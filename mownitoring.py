#!/usr/bin/env python3

import smtplib
import email.mime.text

from http import HTTPStatus

import sqlite3
import subprocess
import syslog
import datetime

import requests
import yaml

CHECKNRPE_BIN = "/usr/local/libexec/nagios/check_nrpe"
CONFIG_FILE = "/etc/mownitoring.yml"
SQLITE_FILE = "/tmp/mownitoring.sqlite"


def notify_pushover(machine, check, message, time_check):
    """Notify through Pushover."""
    alert = f"{time_check}: {machine}!{check} {message}"
    payload = {
        "token": api_cfg["pushover_token"],
        "user": api_cfg["pushover_user"],
        "message": alert,
        "priority": "1",
        "expire": "3600",
        "retry": "90",
        "title": f"Alert from mownitoring: {machine}!{check}"
    }

    p = requests.post(api_cfg["pushover_api_url"], params=payload)
    if p.status_code == HTTPStatus.OK:
        syslog.syslog("Alert sent through pushover")
    else:
        syslog.syslog(syslog.LOG_ERR, "Sending through pushover didn't work")


def notify_syslog(machine, check, message, time_check):
    """Notify through syslog."""
    alert = f"{time_check}: {machine}!{check} {message}"
    syslog.syslog(syslog.LOG_WARNING, alert)


def notify_mail(machine, check, message, time_check):
    """Notify through email."""
    body = ("Hi,\n"
            f"On {time_check}, we detected a change on "
            f"{machine} for the check {check}:\n\n{message}\n\n"
            "Yours truly,\n-- \n"
            "Mownitoring")
    msg = email.mime.text.MIMEText(str(body))
    msg['Subject'] = f"Alert from mownitoring: {machine}!{check}"
    msg['From'] = api_cfg["mail_from"]
    msg['To'] = api_cfg["mail_to"]
    s = smtplib.SMTP(api_cfg["mail_server"])
    s.send_message(msg)
    s.quit()
    syslog.syslog("Alert sent through email")


def craft_sms(machine, check, message, time_check):
    """Create a valuable alert with less text."""
    # keep just the hour, i.e. strip year/month/day
    time_check = time_check[-5:]
    # remove the domain
    machine = machine.split('.')[0]
    alert = f'{time_check} {machine}!{check} {message}'
    return alert[0:156]


def notify_twilio(machine, check, message, time_check):
    """Send a text with twilio."""
    alert = craft_sms(machine, check, message, time_check)
    payload = {
        'From': api_cfg["twilio_sender"],
        'To': "+" + api_cfg["twilio_dest"],
        'Body': alert
    }
    # send the text with twilio's api
    p = requests.post(
        api_cfg["twilio_api_url"],
        data=payload,
        auth=(api_cfg["twilio_account_sid"], api_cfg["twilio_auth_token"]))
    if p.status_code != HTTPStatus.CREATED:
        syslog.syslog(syslog.LOG_ERR, 'Problem while sending twilio')
    syslog.syslog(f'SMS sent with twilio to {api_cfg["twilio_dest"]}')


def check_nrpe(check, host, port):
    """Run a given check for a specified host."""
    nrpe = subprocess.run(
        [CHECKNRPE_BIN,
            "-t", "30", "-H", host, "-c", "check_" + check, "-p", port],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        encoding="utf-8")
    return nrpe.returncode, nrpe.stdout


def check_notifier(notifiers):
    """Check the configured notifier really exists."""
    notifiers_available = {
        "syslog": notify_syslog,
        "pushover": notify_pushover,
        "mail": notify_mail,
        "twilio": notify_twilio
    }
    notifiers_valid = []
    for notifier in notifiers:
        try:
            notifiers_valid.append(notifiers_available[notifier])
        except KeyError:
            syslog.syslog(syslog.LOG_ERR,
                          f"Unknown notifier {notifier} configured")
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
    if status == 255:
        message = "Connection refused"
    c = conn.cursor()
    param = (machine, check)
    try:
        c.execute('SELECT status FROM mownitoring ' +
                  'WHERE machine=? AND check_name=?', param)
        logged_status = c.fetchone()
    except sqlite3.OperationalError:
        logged_status = None
    if logged_status is not None:
        if logged_status[0] != status:
            notify(check, message, machine, notifiers, timestamp)
            if status != 0:
                param = (status, machine, check)
                c.execute('UPDATE mownitoring SET status = ? WHERE ' +
                          'machine=? AND check_name=?', param)
            else:
                param = (machine, check)
                c.execute('DELETE FROM mownitoring ' +
                          'WHERE machine=? AND check_name=?', param)
        else:
            alert = ("Already known state but still a problem for " +
                     f"{machine}!{check}")
            syslog.syslog(alert)
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

    try:
        pushover = {
            "pushover_token":
            yaml_cfg["Alerting_credentials"]["Pushover"]["token"],
            "pushover_user":
            yaml_cfg["Alerting_credentials"]["Pushover"]["user"],
            "pushover_api_url":
            yaml_cfg["Alerting_credentials"]["Pushover"]["api_url"]
        }
        api_cfg.update(pushover)
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Pushover config is wrong or missing")

    try:
        mail = {
            "mail_from": yaml_cfg["Alerting_credentials"]["Mail"]["from"],
            "mail_to": yaml_cfg["Alerting_credentials"]["Mail"]["to"],
            "mail_server": yaml_cfg["Alerting_credentials"]["Mail"]["server"]
        }
        api_cfg.update(mail)
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Mail config is wrong or missing")

    try:
        twilio = {
            "twilio_account_sid":
            yaml_cfg["Alerting_credentials"]["Twilio"]["account_sid"],
            "twilio_auth_token":
            yaml_cfg["Alerting_credentials"]["Twilio"]["auth_token"],
            "twilio_sender":
            yaml_cfg["Alerting_credentials"]["Twilio"]["sender"],
            "twilio_dest":
            yaml_cfg["Alerting_credentials"]["Twilio"]["dest"],
            "twilio_api_url":
            yaml_cfg["Alerting_credentials"]["Twilio"]["api_url"]
        }
        api_cfg.update(twilio)
    except KeyError:
        syslog.syslog(syslog.LOG_ERR, "Twilio config is wrong or missing")

    # monitored machines
    machines = yaml_cfg.copy()
    del machines["Alerting_credentials"]

    return machines


def sqlite_init(sqlite_file):
    """Initialize database."""
    conn = sqlite3.connect(sqlite_file)
    with conn:
        conn.execute('CREATE TABLE IF NOT EXISTS mownitoring (machine TEXT, ' +
                     'check_name TEXT, status INTEGER, mtime INTEGER);')
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
    conn.close()
    syslog.syslog("mownitoring ends")
