# Mownitoring

'My own monitoring'. Which is also a mix between 'monitoring',
'chown.me' (the domain I rent) and it kinda sounds like 'moan'.

# Usage

Copy `mownitoring.yml` in `/etc/` and configures your machines and
their checks. Add the script in your crontab(1) if it suits your need.

# FAQ

## What is the use case?

I don't have many machines to monitor nor I want a complex monitoring
system. It just runs checks and sends notification if needed. Nothing
more.

## How does it work?

It parses the configuration and then for each service of each host,
the script calls check_nrpe to get the return code and the message. If
the return code is not 0 it sends a notification and stores the return
code in a sqlite database. If the return code is different than the
one stored, it sends a notification.

## How do I 'acknowledge' an alert?

You don't. You only get a notification if the service status changes.

## Can I have pretty graphs?

Nope.
