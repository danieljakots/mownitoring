#!/usr/bin/env python3

import unittest
from unittest.mock import Mock, patch

import datetime
import sqlite3
import os

import mownitoring

config_file = "./mownitoring.toml"

SQLITE3_PATH = "/tmp/mownitoring-unittest.sqlite"


# Mock datetime.datetime
class NewDate(datetime.datetime):
    @classmethod
    def now(cls):
        return cls(1970, 1, 1, 9, 0, 0, 0)


class TestMownitoring(unittest.TestCase):
    def setUp(self):
        mownitoring.sqlite_init(SQLITE3_PATH)

    def tearDown(self):
        os.unlink(SQLITE3_PATH)

    def test_readconf(self):
        machines, max_workers, sqlite_file = mownitoring.read_conf(config_file)

        # api_cfg
        self.assertEqual(mownitoring.api_cfg["pushover_token"], "T0k3n")
        self.assertEqual(mownitoring.api_cfg["mail_server"], "localhost")
        self.assertEqual(mownitoring.api_cfg["twilio_account_sid"], "11235811")

        # machines
        self.assertIsInstance(machines["webserver.example.com"][0]["checks"],
                              list)
        self.assertEqual(machines["db.example.com"][2]["connection"]["ip"],
                         "192.0.2.2")
        self.assertIn("mailq", machines["mail.example.com"][0]["checks"])

        self.assertIn("pushover", machines["db.example.com"][1]["alert"])
        self.assertIn("syslog", machines["db.example.com"][1]["alert"])

        self.assertNotIn("T0k3n", machines)
        self.assertNotIn("token", machines)
        self.assertNotIn("Pushover", machines)

    @patch('syslog.syslog')
    def test_check_notifier(self, mock_syslog):
        test1 = mownitoring.check_notifier(["syslog"])
        self.assertIsInstance(test1, list)
        self.assertEqual(test1[0], mownitoring.notify_syslog)

        test2 = mownitoring.check_notifier(["nonexistent"])
        self.assertEqual(test2, [])

        test3 = mownitoring.check_notifier(["syslog", "pushover"])
        self.assertEqual(test3[0], mownitoring.notify_syslog)
        self.assertEqual(test3[1], mownitoring.notify_pushover)

        test4 = mownitoring.check_notifier(["syslog", "nonexistent"])
        self.assertEqual(test4, [mownitoring.notify_syslog])

    @patch('subprocess.run')
    def test_check_nrpe(self, mock_subprocess):
        machines, max_workers, sqlite_file = mownitoring.read_conf(config_file)
        mownitoring.check_nrpe("disk1", "webserver.example.com", "5666")
        mock_subprocess.assert_called_once_with(
            [
                "/usr/local/libexec/nagios/check_nrpe", "-t", "30",
                "-H", "webserver.example.com", "-c", "check_disk1",
                "-p", "5666"
            ],
            stdout=-1,
            stderr=-3,
            encoding='utf-8')

    def test_run_check1(self):
        mownitoring.check_nrpe = Mock()
        mownitoring.check_nrpe.return_value = 2, 'disk nok'
        ts, status, message = mownitoring.run_check("webserver.example.com",
                                                    "5666", "disk1")
        self.assertEqual(2, status)
        self.assertEqual("disk nok", message)

    @patch('syslog.syslog')
    @patch('mownitoring.check_notifier')
    @patch('mownitoring.notify_syslog')
    def test_register_and_alert1(self, mock_notify_syslog1,
                                 mock_check_notifier, mock_syslog1):
        mownitoring.check_nrpe = Mock()
        mownitoring.check_nrpe.return_value = 2, 'disk nok'
        # mock datetime.datetime
        datetime.datetime = NewDate
        mock_check_notifier.return_value = [mownitoring.notify_syslog]
        conn = sqlite3.connect(SQLITE3_PATH)
        ts, status, message = mownitoring.run_check("webserver.example.com",
                                                    "5666", "disk1")
        mownitoring.register_and_alert("disk1", "webserver.example.com",
                                       "5666", "webserver.example.com",
                                       ["syslog"], conn, ts, status, message)
        mock_notify_syslog1.assert_called_once_with(
            "webserver.example.com", "disk1", "disk nok", "1970/01/01 09:00")
        conn.close()

    @patch('syslog.syslog')
    @patch('mownitoring.check_notifier')
    @patch('mownitoring.notify_pushover')
    def test_register_and_alert2(self, mock_notify_pushover,
                                 mock_check_notifier, mock_syslog):
        mock_check_notifier.return_value = [mock_notify_pushover]
        conn = sqlite3.connect(SQLITE3_PATH)
        with conn:
            conn.execute("INSERT INTO mownitoring VALUES ('db.example.com', " +
                         "'disk1', 2, 1519300000)")
        ts, status, message = (1519300060, 2, "disk nok")
        mownitoring.register_and_alert("disk1", "db.example.com", "5667",
                                       "db.example.com", ["pushover"],
                                       conn, ts, status, message)
        mock_notify_pushover.assert_not_called()
        conn.close()

    @patch('syslog.syslog')
    @patch('smtplib.SMTP')
    @patch('email.mime.text.MIMEText')
    def test_notify_mail(self, mock_mimetext, mock_smtp, mock_syslog):
        # we need api_cfg
        mownitoring.read_conf(config_file)
        test_body = ("Hi,\n"
                     "On 1970/01/01 09:00, we detected a change on "
                     "webserver.example.com for the check disk1:\n\n"
                     "disk nok\n\n"
                     "Yours truly,\n-- \n"
                     "Mownitoring")
        mownitoring.notify_mail("webserver.example.com", "disk1", "disk nok",
                                "1970/01/01 09:00")
        mock_mimetext.assert_called_once_with(str(test_body))

    def test_craft_sms(self):
        message = (
            "disk very very full, like totally blahblah full partition, "
            "blahblah other fullpartition, blahblah third partition "
            "completely full, oh and inodes are full too btw")
        reallyis = mownitoring.craft_sms("webserver.example.com", "disk1",
                                         message, "1970/01/01 09:00")
        shouldbe = ("09:00 webserver!disk1 disk very very full, like totally "
                    "blahblah full partition, blahblah other fullpartition, "
                    "blahblah third partition completely full, oh ")
        self.assertEqual(reallyis, shouldbe)


if __name__ == '__main__':
    unittest.main()
