#!/usr/bin/env python3

import syslog

import yaml

CONFIG_FILE = "/etc/mownitoring.yml"


def readconf(config_file):
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

    # twilio api key
    try:
        api_cfg["twilio_account_sid"] = yaml_cfg["Twilio"]["account_sid"]
        api_cfg["twilio_auth_token"] = yaml_cfg["Twilio"]["auth_token"]
        api_cfg["twilio_available_number"] = yaml_cfg["Twilio"]["sender"]
        api_cfg["twilio_api_url"] = yaml_cfg["Twilio"]["api_url"]
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Twilio config couldn't be parsed")

    machines = {}
    for machine in yaml_cfg["machines"]:
        machines[machine] = []
        machines[machine].append({})
        machines[machine][0]["checks"] = []
        for check in yaml_cfg[machine][0]["checks"]:
            machines[machine][0]["checks"].append(check)

        machines[machine].append({})
        machines[machine][1]["connection"] = {}
        machines[machine][1]["connection"]["ip"] = yaml_cfg[machine][1]["connection"]["ip"]
        machines[machine][1]["connection"]["port"] = yaml_cfg[machine][1]["connection"]["port"]

        machines[machine].append({})
        machines[machine][2]["alert"] = []
        for alert in yaml_cfg[machine][2]["alert"]:
            machines[machine][2]["alert"].append(alert)

    return machines


if __name__ == "__main__":
    machines = readconf(CONFIG_FILE)
    print(machines)
    for machine in machines.keys():
        print(machine)
