#!/usr/bin/env python3

import smtplib
import email.mime.text

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
    syslog.syslog("Alert sent through pushover")


def notify_syslog(alert):
    """Notify through syslog."""
    syslog.syslog(syslog.LOG_WARNING, alert)


def notify_mail(alert):
    """Notify through email."""
    body = (
        "Hi,\n",
        "We detected a problem:\n",
        alert,
        "Yours truly,\n",
        "Mownitoring"
    )
    msg = email.mime.text.MIMEText(str(body))
    msg['Subject'] = "Alert from mownitoring"
    msg['From'] = api_cfg["mail_from"]
    msg['To'] = api_cfg["mail_to"]
    s = smtplib.SMTP(api_cfg["mail_server"])
    s.send_message(msg)
    s.quit()
    syslog.syslog("Alert sent through email")


def check_nrpe(check, host, port):
    """Run a given check for a specified host."""
    nrpe = subprocess.run(["/usr/local/libexec/nagios/check_nrpe",
                           "-H" + host,
                           "-ccheck_" + check,
                           "-p" + port],
                          stdout=subprocess.PIPE,
                          universal_newlines=True)
    return nrpe.returncode, nrpe.stdout


def check_notifier(notifiers):
    """Check the configured notifier really exists."""
    notifiers_available = {"syslog": notify_syslog,
                           "pushover": notify_pushover,
                           "mail": notify_mail}
    notifiers_valid = []
    for notifier in notifiers:
        try:
            notifiers_valid.append(notifiers_available[notifier])
        except KeyError:
            syslog.syslog(syslog.LOG_ERR, "Unknown notifier " + notifier +
                          " configured")
    return notifiers_valid


def check_status(check, host, port, machine, notifiers):
    """Check the status of the check, and alert if needed."""
    status, message = check_nrpe(check, host, port)
    if status != 0:
        notifiers_valid = check_notifier(notifiers)
        if notifiers_valid:
            for notifier in notifiers_valid:
                notifier(machine + "!" + check + " " + message)
        else:
            syslog.syslog(syslog.LOG_ERR, "No valid notify system")


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
            yaml_cfg["Alerting_credentials"][0]["Pushover"]["api_url"],
            "mail_from":
            yaml_cfg["Alerting_credentials"][1]["Mail"]["from"],
            "mail_to":
            yaml_cfg["Alerting_credentials"][1]["Mail"]["to"],
            "mail_server":
            yaml_cfg["Alerting_credentials"][1]["Mail"]["server"]
            }
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Alerting_cred couldn't be parsed")

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
            check_status(check, host, port, machine,
                         machines[machine][1]["alert"])
    syslog.syslog("mownitoring ends")
