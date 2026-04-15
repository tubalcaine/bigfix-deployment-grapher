# bigfix-deployment-grapher

Generates graphs of BigFix deployment infrastructure using [Graphviz](https://graphviz.org/),
showing relay hierarchy and endpoint distributions. Endpoints can be grouped and counted
by any BigFix computer property (subnet, OS, location, etc.).

## Requirements

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Graphviz binaries installed and on your PATH — standard on most Linux distributions,
  available for Windows/macOS/FreeBSD at https://graphviz.org/download/

## Setup

```bash
uv sync                  # create .venv and install all dependencies
uv run python src/bf_deployment_map.py [options]

# Or activate the environment first:
source .venv/bin/activate
python src/bf_deployment_map.py [options]
```

## Usage

```
usage: bf_deployment_map.py [-h] [-b BFSERVER] [-p BFPORT] [-u BFUSER]
                            [-P BFPASS] [-k KEYCREDS] [-s SETCREDS]
                            [-w WRITEJSON] [-j JSON] [-o OUTPUT] [-e ENGINE]
                            [-f FORMAT] [-g GROUP_PROPERTY] [-m MAP] [-r] [-d]
                            [-l] [-E FILE]
```

### Connection

| Switch | Long | Description |
|--------|------|-------------|
| `-b` | `--bfserver` | BigFix REST Server hostname or IP address |
| `-p` | `--bfport` | BigFix port number (default: 52311) |
| `-u` | `--bfuser` | BigFix console/REST username |
| `-P` | `--bfpass` | Password on the command line (see Password Management below) |

You must supply either `--json` (cached data) or `--bfserver` + `--bfuser`. The password
can be supplied via `--bfpass`, retrieved from the keyring via `--keycreds`, or entered
interactively (no-echo prompt) if neither is given.

### Password Management

Storing your password in a keyring avoids exposing it on the command line or being
prompted on every run.

| Switch | Long | Description |
|--------|------|-------------|
| `-s KEY` | `--setcreds KEY` | Prompt for password and store it under KEY in the keyring, then exit |
| `-k KEY` | `--keycreds KEY` | Retrieve the password stored under KEY from the keyring |
| `-E FILE` | `--encrypted-keyring FILE` | Use an encrypted keyring file at FILE instead of the system keyring |

**System keyring (default):** Uses the OS credential store (GNOME Keyring, KWallet,
macOS Keychain, Windows Credential Manager, etc.).

```bash
# Store credentials once
python src/bf_deployment_map.py -s mylab -u IEMAdmin

# Run using stored credentials
python src/bf_deployment_map.py -b 10.1.1.1 -u IEMAdmin -k mylab
```

**Encrypted keyring file (`-E`):** A portable alternative backed by
`keyrings.alt.file.EncryptedKeyring` — useful on headless systems or when you want
a self-contained credential file. The file is AES256-encrypted and password-protected.

```bash
# Store credentials in an encrypted file
python src/bf_deployment_map.py -s mylab -u IEMAdmin -E ~/bf-creds.cfg

# Run using the encrypted file
python src/bf_deployment_map.py -b 10.1.1.1 -u IEMAdmin -k mylab -E ~/bf-creds.cfg
```

### Data Source

| Switch | Long | Description |
|--------|------|-------------|
| `-w FILE` | `--writejson FILE` | Save API query results to a JSON file for reuse |
| `-j FILE` | `--json FILE` | Load data from a previously saved JSON file instead of querying |

On large deployments, REST queries can be slow. Use `-w` to cache results and `-j` to
re-render without re-querying:

```bash
# Query the server and cache results
python src/bf_deployment_map.py -b 10.1.1.1 -u IEMAdmin -k mylab -w data.json -o MyGraph

# Re-render from cache (no server needed)
python src/bf_deployment_map.py -j data.json -o MyGraph -f pdf,svg
```

### Output

| Switch | Long | Description |
|--------|------|-------------|
| `-o PREFIX` | `--output PREFIX` | Output filename base (default: `./DeploymentMap`) |
| `-f FMT` | `--format FMT` | Output format(s), comma-separated (default: `pdf`). Any format supported by Graphviz: `pdf`, `png`, `svg`, `ps`, etc. |
| `-e ENGINE` | `--engine ENGINE` | Graphviz layout engine (default: `dot`). Other options: `neato`, `circo`, `twopi`, etc. |
| `-l` | `--letter` | Scale and tile the output to US Letter portrait pages (8.5"×11"). Default is natural size with no page constraints. |

The Graphviz source file is saved as `<output>.<engine>` (e.g., `DeploymentMap.dot`).
Rendered output is saved as `<output>.<format>` (e.g., `DeploymentMap.pdf`).

### Graph Content

| Switch | Long | Description |
|--------|------|-------------|
| `-g PROP` | `--group-property PROP` | BigFix computer property to group endpoints by (default: `Subnet Address`). Ignored with `--relaysonly` or `--detail`. |
| `-m MAP` | `--map MAP` | Relay name mappings: `fromName:toName[,fromName:toName...]`. Useful when endpoints report to a relay by IP address rather than hostname. |
| `-r` | `--relaysonly` | Render relay hierarchy only — no endpoints or groups |
| `-d` | `--detail` | Create one node per endpoint instead of grouping (can produce very large graphs) |

**Rendering modes (mutually exclusive in practice):**

| Mode | Switches | Shows |
|------|----------|-------|
| Relays only | `--relaysonly` | Root server + relay nodes with endpoint counts |
| Grouped (default) | *(neither)* | Root + relays + one group node per unique property value per relay |
| Detail | `--detail` | Root + relays + one node per individual endpoint |

## Examples

```bash
# Relay hierarchy only
python src/bf_deployment_map.py -b 10.1.1.1 -u IEMAdmin -k mylab --relaysonly -o RelayMap

# Group by OS (default portrait size)
python src/bf_deployment_map.py -b 10.1.1.1 -u IEMAdmin -k mylab -g OS -o OSMap

# Group by OS, scaled to US Letter pages for printing
python src/bf_deployment_map.py -b 10.1.1.1 -u IEMAdmin -k mylab -g OS --letter -o OSMap

# Map an external IP to a known relay (DMZ/NAT scenario), multiple output formats
python src/bf_deployment_map.py -b 10.1.1.1 -u IEMAdmin -k mylab \
    -m 203.0.113.45:dmz-relay -f pdf,svg -o DeploymentMap

# Use cached data, detail mode
python src/bf_deployment_map.py -j data.json --detail -o DetailMap
```
