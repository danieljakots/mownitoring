[![Build Status](https://travis-ci.org/danieljakots/mownitoring.svg?branch=master)](https://travis-ci.org/danieljakots/mownitoring)

# Mownitoring

'My own monitoring'. Which is also a mix between 'monitoring',
'chown.me' (the domain I rent) and it kinda sounds like 'moan'.

# Usage

Copy `mownitoring.yml` in `/etc/` and configure your machines and
their checks. Add the script in your crontab(1) if it suits your needs.

If you don't want to use the default path, you can call the script with your
config file as an argument: `/path/to/mownitoring.py /path/to/mownitoring.yml`

# FAQ

## What are the requirements?

Python 3.6 and the following libraries: requests and yaml. You also need
check_nrpe (*nrpe* package on OpenBSD).

## What is the use case?

I don't have many machines to monitor nor I want a complex monitoring
system. It just runs checks and sends notification if needed. Nothing
more.

## How does it work?

It parses the configuration and then for each service of each host,
the script calls check_nrpe to get the return code and the message. If
the return code is not 0 it sends a notification and stores the return
code in a sqlite database. If the return code is different than the
one stored, it sends a notification. It abides by the rule: *You only notify
once*.

## What are the supported notification systems?

* [Pushover](https://pushover.net/)
* email
* [Twilio](https://www.twilio.com/)

It also logs to syslog what is happening (but that's not really a
notification system per se).

## How do I 'acknowledge' an alert?

You don't. You only get a notification if the service status changes.

## Can I have pretty graphs?

Nope.
