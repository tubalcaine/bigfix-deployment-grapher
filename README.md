# bigfix-deployment-grapher

This project will graph the relay relationships in a BigFix deployment,
providing a roll-up of endpoints grouped by an arbitrary computer property,
including counts.

It also has options for plotting all the endpoints, resulting in a larger
and busier graph. This is very much a work in progress, as it depends on
graphviz (https://graphviz.org/download/), which is a standard package
on most Linux systems and is avaiable as a binary install on Windows.
This will need the grpahviz "dot" tool (and others depending on features you
try) to be on your PATH, so I recommend you choose that option on install.

