"""
bf_deployment_map.py - A script to graph BigFix deployment using GraphViz

Draws diagrams of BigFix deployments
"""

import argparse
import ipaddress
import json
import sys
from getpass import getpass
import graphviz
import keyring
from besapi.besapi import BESConnection

## BFDeploymentMap
##
## Original author: Michael Schwarz
## michael.schwarz@hcl.com
## mschwarz@multitool.net
##
## Released under the Apache 2 License
##
## A python script to generate a graph of a BigFix deployment using the widely available
## open source graphing tool, Graphviz (https://graphviz.org/)
## Graphviz must be installed and on the PATH for this script to work properly.
##
## Graphviz is a standard package on almost all Linux distributions, and is available
## for download for Windows, MacOS, Solaris, and FreeBSD here:
##
## https://graphviz.org/download/


def _prompt_password_twice(username):
    """Prompt for a password twice for verification; return the confirmed password."""
    first_pass = "not"
    second_pass = ""
    while first_pass != second_pass:
        if first_pass != "not":
            print("\nPasswords did not match. Try again.\n")
        first_pass = getpass(f"BigFix password for {username}: ")
        second_pass = getpass("Enter the password again: ")
    return first_pass


def set_secure_credentials(service_name, user_name):
    """Prompt for a password and store it in the keyring under service_name."""
    print(f"Enter the password for the user {user_name}")
    print("The password will not display. You must enter the same")
    print("password twice in a row. It will be stored encrypted")
    print(f"under the key name {service_name} in your system's")
    print("secure credential store. Use the command switches:")
    print(f"  -k {service_name} -u {user_name}    --OR--")
    print(f"  --keycreds {service_name} --bfuser {user_name}")
    print("to run the program without having to provide the password.")
    keyring.set_password(service_name, user_name, _prompt_password_twice(user_name))


def build_arg_parser():
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-b", "--bfserver", type=str, help="BigFix REST Server name/IP address"
    )
    parser.add_argument(
        "-p", "--bfport", type=int, help="BigFix Port number (default 52311)", default=52311
    )
    parser.add_argument("-u", "--bfuser", type=str, help="BigFix Console/REST User name")
    parser.add_argument("-P", "--bfpass", type=str, help="BigFix Console/REST Password")
    parser.add_argument(
        "-k", "--keycreds", type=str,
        help="Use stored credentials by key name. Ex: -k mykey"
    )
    parser.add_argument(
        "-s", "--setcreds", type=str,
        help="Store credentials under key name and exit. Ex: -s mykey"
    )
    parser.add_argument(
        "-w", "--writejson", type=str,
        help="Write query results to json file for reuse."
    )
    parser.add_argument(
        "-j", "--json", type=str,
        help="Use JSON from previous run instead of doing REST query",
    )
    parser.add_argument(
        "-o", "--output", type=str, help="Output file base name", default="./DeploymentMap"
    )
    parser.add_argument(
        "-e", "--engine", type=str,
        help="Specify the graphviz layout engine (dot, neato, etc.)",
        default="dot",
    )
    parser.add_argument(
        "-f", "--format", type=str,
        help="Specify the output format(s) -f <fmt>[,<fmt>]",
        default="pdf",
    )
    parser.add_argument(
        "-g", "--group-property", type=str,
        help="Name of BigFix Computer Property to group endpoints by (default mode only; "
             "ignored with --relaysonly or --detail)",
        default="Subnet Address",
    )
    parser.add_argument(
        "-m", "--map", type=str,
        help="Relay name map fromName:toName[,fromName:toName...]"
    )
    parser.add_argument(
        "-r", "--relaysonly", action="store_true",
        help="Render relays only, no endpoints or groups"
    )
    parser.add_argument(
        "-d", "--detail", action="store_true",
        help="Create one node per endpoint instead of grouping (overrides --group-property)"
    )
    parser.add_argument(
        "-l", "--letter", action="store_true",
        help='Tile output to US Letter portrait pages (8.5"x11"). '
             "Default is natural size with no page constraints.",
    )
    parser.add_argument(
        "-E", "--encrypted-keyring", type=str, metavar="FILE",
        help="Use an encrypted keyring file at FILE instead of the system keyring.",
    )
    return parser


def _configure_keyring(args):
    """If --encrypted-keyring was given, activate that backend before any keyring I/O."""
    if args.encrypted_keyring is None:
        return
    import keyrings.alt.file

    class _CustomEncryptedKeyring(keyrings.alt.file.EncryptedKeyring):
        @property
        def file_path(self):
            return args.encrypted_keyring

    keyring.set_keyring(_CustomEncryptedKeyring())


def _validate_args(parser, args):
    """Validate argument combinations; call parser.error() on failure."""
    if args.setcreds is not None:
        if not args.bfuser:
            parser.error("--bfuser is required with --setcreds\n")
    elif not args.json:
        if not args.bfserver or not args.bfuser:
            parser.error(
                "You must specify either --json, --setcreds, or the BigFix REST "
                "parameters (--bfserver, --bfuser)\n"
            )


def resolve_password(args):
    """Return the BigFix password from keyring, --bfpass, or interactive prompt."""
    if args.keycreds is not None:
        bf_pass = keyring.get_password(args.keycreds, args.bfuser)
        if bf_pass is None:
            sys.exit(
                f"Error: no credentials found in keyring for key '{args.keycreds}' "
                f"and user '{args.bfuser}'"
            )
        return bf_pass
    if args.bfpass is not None:
        return args.bfpass
    print(f"Enter the password for the user {args.bfuser}")
    print("The password will not display. You must enter the same")
    print("password twice in a row for verification.")
    return _prompt_password_twice(args.bfuser)


def find_endpoint_relay(relay_name, relay, ip_idx, relay_map):
    """Locate the relay entry for an endpoint using three fallback strategies:
    direct name match, IP address index, then relay name map."""
    if relay_name in relay:
        return relay[relay_name]
    if relay_name in ip_idx:
        return ip_idx[relay_name]
    mapped = relay_map.get(relay_name)
    if mapped is not None and mapped in relay:
        return relay[mapped]
    return None


def build_relay_tree(comp_list, relay_map, bfport):
    """Process a flat list of BigFix computer records into a relay hierarchy dict.

    Returns a dict keyed by relay hostname. Each entry contains the relay's
    component record, total endpoint count, grouped endpoint data, and parent
    relay name.
    """
    relay = {}
    ip_idx = {}

    for comp in comp_list:
        if comp[4] is True:
            # Root server — its own parent by convention
            root = comp[1]
            parent = relay_map.get(comp[1], comp[1])
            relay[root] = {"comp": comp, "count": 1, "groups": {}, "parent": parent}
            for ip in str(comp[6]).split("|"):
                ip_idx[ip] = relay[root]

        elif comp[3] is True:
            # Relay server
            relay_host = comp[1]
            raw_parent = str(comp[5]).split(f":{bfport}", maxsplit=1)[0]
            parent = relay_map.get(raw_parent, raw_parent)
            relay[relay_host] = {"comp": comp, "count": 1, "groups": {}, "parent": parent}
            for ip in str(comp[6]).split("|"):
                ip_idx[ip] = relay[relay_host]

        else:
            # Endpoint — find its relay and increment counts
            relay_name = str(comp[5]).split(f":{bfport}", maxsplit=1)[0]

            try:
                ip_addr = ipaddress.ip_address(relay_name)
            except ValueError:
                ip_addr = None

            # Strip domain suffix from hostnames (not IPs)
            if not ip_addr and "." in relay_name:
                relay_name = relay_name.split(".")[0]

            ep_relay = find_endpoint_relay(relay_name, relay, ip_idx, relay_map)

            if ep_relay is None:
                print(
                    f"Warning: could not locate relay '{relay_name}' "
                    "using name, IP address, or relay map"
                )
                continue

            ep_relay["count"] += 1
            for grp in str(comp[7]).split("|"):
                if grp in ep_relay["groups"]:
                    ep_relay["groups"][grp]["count"] += 1
                    ep_relay["groups"][grp]["comp_list"].append(comp)
                else:
                    ep_relay["groups"][grp] = {"count": 1, "comp_list": [comp]}

    # Second pass: resolve parent names where FQDN/short-name mismatch exists
    # (e.g. parent stored as "relay.corp.com" but relay keyed as "relay")
    for r in list(relay.keys()):
        p = relay[r]["parent"]
        if p == r or p in relay:
            continue
        resolved = None
        if "." in p:
            short = p.split(".")[0]
            if short in relay:
                resolved = short
        else:
            for key in relay:
                if key.startswith(p + "."):
                    resolved = key
                    break
        if resolved is not None:
            print(f"Info: relay '{r}' parent resolved '{p}' -> '{resolved}'")
            relay[r]["parent"] = resolved
        else:
            print(f"Warning: relay '{r}' parent '{p}' not found in relay dict")

    return relay


def load_relay_data(args, bf_pass):
    """Return (relay dict, server_conf dict) from a JSON cache or live REST query."""
    if args.json:
        with open(args.json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data["relay"], data["cnf"]

    server_conf = {"bfserver": args.bfserver, "bfport": args.bfport}

    relay_query = f"""(id of it, name of it as lowercase,
    last report time of it, relay server flag of it,
    root server flag of it, relay server of it as lowercase,
    concatenation "|" of (ip addresses of it as string),
    concatenation "|" of
    values of property results whose (name of property of it = "{args.group_property}") of it
    )
    of bes computers whose (relay server flag of it or root server flag of it)
    """.strip()

    endpoint_query = f"""(id of it, name of it as lowercase,
    last report time of it, relay server flag of it,
    root server flag of it, relay server of it as lowercase,
    concatenation "|" of (ip addresses of it as string),
    concatenation "|" of
    values of property results whose (name of property of it = "{args.group_property}") of it
    )
    of bes computers whose (not relay server flag of it and not root server flag of it)
    """.strip()

    relay_map = {}
    if args.map:
        for entry in str(args.map).split(","):
            name, value = entry.split(":")
            relay_map[name] = value

    bf = BESConnection(
        args.bfuser, bf_pass, f"https://{args.bfserver}:{args.bfport}", verify=False
    )

    relay_result = bf.post("query", {"relevance": relay_query, "output": "json"})
    if relay_result.request.status_code != 200:
        sys.exit("Error: relay/root server query failed.")

    endpoint_result = bf.post("query", {"relevance": endpoint_query, "output": "json"})
    if endpoint_result.request.status_code != 200:
        sys.exit("Error: endpoint query failed.")

    comp_list = (
        json.loads(relay_result.text)["result"]
        + json.loads(endpoint_result.text)["result"]
    )

    relay = build_relay_tree(comp_list, relay_map, args.bfport)

    if args.writejson:
        with open(args.writejson, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"relay": relay, "cnf": server_conf}, sort_keys=True, indent=2))

    return relay, server_conf


def render_graph(relay, server_conf, args):
    """Build and render the Graphviz diagram from the relay hierarchy."""
    dot = graphviz.Digraph(
        server_conf["bfserver"] + ":" + str(server_conf["bfport"]), engine=args.engine
    )

    # Layout attributes applied in all cases
    dot.attr(
        # Hierarchy direction: endpoints at bottom, root server at top
        rankdir="BT",
        # Orthogonal edge routing: right-angle bends suit a strict hierarchy and
        # consume less routing space than the default spline curves.
        splines="ortho",
        # Tighter node spacing to fit more nodes per page.
        # nodesep: min horizontal gap between nodes on the same rank (default 0.25)
        # ranksep: min vertical gap between ranks (default 0.5)
        nodesep="0.15",
        ranksep="0.4",
        # Merge parallel edges where possible to reduce clutter.
        concentrate="true",
        fontsize="11",
    )
    # Page-sizing attributes: only applied when --letter is requested.
    # Without --letter, Graphviz renders the graph at its natural size.
    if args.letter:
        dot.attr(
            # Constrain width to 7.5" (letter minus 0.5" margins each side),
            # uncapped height so the diagram grows as tall as it needs to.
            size="7.5,999",
            # Tile onto US Letter portrait pages. pagedir=TL means the top-left
            # tile is page 1, so the root server (top of graph) appears first and
            # subsequent pages extend downward. Pages join on their short (8.5") edges.
            page="8.5,11",
            pagedir="TL",
            margin="0.5",
        )
    dot.attr("node", fontsize="9", fontname="Arial", margin="0.1,0.05")

    for relay_idx, relay_host in enumerate(relay.keys()):
        relay_data = relay[relay_host]
        dot.node(
            relay_host,
            color="red",
            shape="box3d",
            root=str(relay_data["comp"][4]),
            label=f"{relay_host} - {relay_data['count']} unique endpoints\n",
        )
        if relay_data["parent"] in relay:
            dot.edge(relay_host, relay_data["parent"], penwidth="1.5")
        else:
            print(
                f"Warning: skipping edge '{relay_host}' -> '{relay_data['parent']}'"
                " — parent not in relay dict"
            )

        if not args.relaysonly:
            for grp_idx, (c, grp) in enumerate(relay_data["groups"].items()):
                if args.detail:
                    for ep in grp["comp_list"]:
                        dot.node(ep[1], color="blue", shape="component")
                        dot.edge(ep[1], relay_host, penwidth="1.5")
                else:
                    grp_node = f"grpnode_{relay_idx}_{grp_idx}"
                    dot.node(
                        grp_node,
                        color="green",
                        label=f"{args.group_property}: {c}\n{grp['count']} endpoints",
                        shape="box",
                    )
                    dot.edge(grp_node, relay_host, penwidth="1.5")

    for fmt in args.format.split(","):
        dot.unflatten(stagger=3).render(
            filename=f"{args.output}.{args.engine}",
            outfile=f"{args.output}.{fmt.strip()}",
            format=fmt.strip(),
        )


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    _configure_keyring(args)
    _validate_args(parser, args)

    if args.setcreds is not None:
        set_secure_credentials(args.setcreds, args.bfuser)
        sys.exit(0)

    bf_pass = None if args.json else resolve_password(args)
    relay, server_conf = load_relay_data(args, bf_pass)
    render_graph(relay, server_conf, args)
    print("Done.")


if __name__ == "__main__":
    main()
