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


def check_alert(check, host, port, machine):
    """Check, and alert if needed."""
    status, message = check_nrpe(check, host, port)
    if status != 0:
        notify_pushover(machine + " " + message)


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
        api_cfg["pushover_token"] = yaml_cfg["Pushover"]["token"]
        api_cfg["pushover_user"] = yaml_cfg["Pushover"]["user"]
        api_cfg["pushover_api_url"] = yaml_cfg["Pushover"]["api_url"]
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Pushover config couldn't be parsed")

    # monitored machines
    machines = {}
    for machine in yaml_cfg["machines"]:
        machines[machine] = []
        machines[machine].append({})
        machines[machine][0]["checks"] = []
        for check in yaml_cfg[machine][0]["checks"]:
            machines[machine][0]["checks"].append(check)

        machines[machine].append({})
        machines[machine][1]["alert"] = []
        for alert in yaml_cfg[machine][1]["alert"]:
            machines[machine][1]["alert"].append(alert)

        try:
            machines[machine].append({})
            machines[machine][2]["connection"] = {}
            machines[machine][2]["connection"]["ip"] = yaml_cfg[machine][2]["connection"]["ip"]
            machines[machine][2]["connection"]["port"] = yaml_cfg[machine][2]["connection"]["port"]
        except IndexError:
            pass

    return machines


def main():
    syslog.syslog("mownitoring starts")
    for machine in machines.keys():
        for check in machines[machine][0]["checks"]:
            try:
                host = machines[machine][2]["connection"]["ip"]
                port = machines[machine][2]["connection"]["port"]
            except KeyError:
                host = machine
                port = "5666"
            check_alert(check, host, port, machine)
    syslog.syslog("mownitoring ends")


if __name__ == "__main__":
    machines = read_conf(CONFIG_FILE)
    main()
