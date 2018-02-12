#!/usr/bin/env python3

import subprocess
import syslog

import requests
import yaml

CONFIG_FILE = "/etc/mownitoring.yml"


def notify_pushover(alert):
    """Send a pushover notification."""
    payload = {"token": api_cfg["pushover_token"],
               "user": api_cfg["pushover_user"],
               "message": alert}

    requests.post(api_cfg["pushover_api_url"], params=payload)


def notify_syslog(alert):
    syslog.syslog(alert)


def check_nrpe(check, host, port):
    """Run a given check for a specified host."""
    nrpe = subprocess.run(["/usr/local/libexec/nagios/check_nrpe",
                           "-H" + host,
                           "-ccheck_" + check,
                           "-p" + port],
                          stdout=subprocess.PIPE,
                          universal_newlines=True)
    return nrpe.returncode, nrpe.stdout


def notify(notifiers, message):
    notifiers_available = {"syslog": notify_syslog,
                           "pushover": notify_pushover}
    try:
        for notifier in notifiers:
            notifiers_available[notifier](message)
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Unknown notifier configured")


def check_alert(check, host, port, machine, notifiers):
    """Check, and alert if needed."""
    status, message = check_nrpe(check, host, port)
    if status != 0:
        notify(notifiers, machine + "!" + check + " " + message)


def read_conf(config_file):
    """Parse the configuration file.

    It uses 2 data structures:
    - api_cfg: a global dict that contains the API keys
    - machines: a *returned* dict with informations about the machines
      we're monitoring
    """
    with open(config_file, 'r') as ymlfile:
        yaml_cfg = yaml.load(ymlfile)

    global api_cfg
    api_cfg = {}
    # pushover
    try:
        api_cfg = {
            "pushover_token":
            yaml_cfg["Alerting_credentials"][0]["Pushover"]["token"],
            "pushover_user":
            yaml_cfg["Alerting_credentials"][0]["Pushover"]["user"],
            "pushover_api_url":
            yaml_cfg["Alerting_credentials"][0]["Pushover"]["api_url"]
            }
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Pushover config couldn't be parsed")

    # monitored machines
    machines = yaml_cfg.copy()
    del machines["Alerting_credentials"]

    return machines

if __name__ == "__main__":
    syslog.syslog("mownitoring starts")
    machines = read_conf(CONFIG_FILE)
    for machine in machines["machines"]:
        for check in machines[machine][0]["checks"]:
            try:
                host = machines[machine][2]["connection"]["ip"]
                port = machines[machine][2]["connection"]["port"]
            except IndexError:
                host = machine
                port = "5666"
            check_alert(check, host, port, machine,
                        machines[machine][1]["alert"])
    syslog.syslog("mownitoring ends")
