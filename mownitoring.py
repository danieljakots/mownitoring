#!/usr/bin/env python3

import smtplib
import email.mime.text

import sqlite3
import subprocess
import syslog
import datetime

import requests
import yaml

CONFIG_FILE = "/etc/mownitoring.yml"
SQLITE_FILE = "/tmp/mownitoring.sqlite"


def notify_pushover(machine, check, message, time_check):
    """Notify through Pushover."""
    alert = time_check + ": " + machine + "!" + check + " " + message
    payload = {"token": api_cfg["pushover_token"],
               "user": api_cfg["pushover_user"],
               "message": alert,
               "priority": "1",
               "expire": "3600",
               "retry": "90",
               "title": "Alert from mownitoring: " + machine + "!" + check}

    p = requests.post(api_cfg["pushover_api_url"], params=payload)
    if p.status_code == 200:
        syslog.syslog("Alert sent through pushover")
    else:
        syslog.syslog(syslog.LOG_ERR, "Sending through pushover didn't work")


def notify_syslog(machine, check, message, time_check):
    """Notify through syslog."""
    alert = time_check + ": " + machine + "!" + check + " " + message
    syslog.syslog(syslog.LOG_WARNING, alert)


def notify_mail(machine, check, message, time_check):
    """Notify through email."""
    body = (
        "Hi,\n"
        "On " + time_check + ", we detected a change on "
        "" + machine + " for the check " + check + ":\n\n"
        "" + message + "\n\n"
        "Yours truly,\n-- \n"
        "Mownitoring"
    )
    msg = email.mime.text.MIMEText(str(body))
    msg['Subject'] = "Alert from mownitoring: " + machine + "!" + check
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


def notify(check, message, machine, notifiers, timestamp):
    """Send an alert to notification system(s)."""
    notifiers_valid = check_notifier(notifiers)
    if notifiers_valid:
        for notifier in notifiers_valid:
            time_check = timestamp.strftime('%Y/%m/%d %H:%M')
            notifier(machine, check, message, time_check)
    else:
        syslog.syslog(syslog.LOG_ERR, "No valid notify system")


def check_status(check, host, port, machine, notifiers, conn):
    """Choose if we send an alert."""
    timestamp = datetime.datetime.now()
    status, message = check_nrpe(check, host, port)
    c = conn.cursor()
    param = (machine, check)
    try:
        c.execute('SELECT status FROM mownitoring ' +
                  'WHERE machine=? AND check_name=?', param)
    except sqlite3.OperationalError:
        pass
    logged_status = c.fetchone()
    if logged_status:
        if logged_status[0] != status:
            notify(check, message, machine, notifiers, timestamp)
        else:
            if logged_status[0] != 0:
                alert = ("Already known state but still a problem for " +
                         machine + "!" + check)
                syslog.syslog(alert)
        if status == 0:
            param = (machine, check)
            c.execute('DELETE FROM mownitoring ' +
                      'WHERE machine=? AND check_name=?', param)
    else:
        if status != 0:
            param = (machine, check, status, timestamp.strftime('%s'))
            c.execute("INSERT INTO mownitoring VALUES (?, ?, ?, ?)", param)
            notify(check, message, machine, notifiers, timestamp)
    conn.commit()


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


def sqlite_init(sqlite_file):
    """Initialize database."""
    conn = sqlite3.connect(sqlite_file)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS mownitoring (machine TEXT, ' +
              'check_name TEXT, status INTEGER, mtime INTEGER);')
    conn.commit()
    return conn


if __name__ == "__main__":
    syslog.syslog("mownitoring starts")
    machines = read_conf(CONFIG_FILE)
    conn = sqlite_init(SQLITE_FILE)
    for machine in machines["machines"]:
        for check in machines[machine][0]["checks"]:
            try:
                host = machines[machine][2]["connection"]["ip"]
                port = machines[machine][2]["connection"]["port"]
            except IndexError:
                host = machine
                port = "5666"
            check_status(check, host, port, machine,
                         machines[machine][1]["alert"], conn)
    conn.commit()
    syslog.syslog("mownitoring ends")
