#!/usr/bin/env python3

import unittest
from unittest.mock import Mock, patch

import mownitoring

config_file = "./mownitoring.yml"


class TestMownitoring(unittest.TestCase):

    def test_readconf(self):
        machines = mownitoring.read_conf(config_file)

        # api_cfg
        self.assertEqual(mownitoring.api_cfg["pushover_token"],
                         "T0k3n")
        self.assertEqual(mownitoring.api_cfg["mail_server"],
                         "localhost")

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
        mownitoring.check_nrpe("disk1", "webserver.example.com", "5666")
        mock_subprocess.assert_called_once_with(["/usr/local/libexec/" +
                                                 "nagios/check_nrpe",
                                                 "-Hwebserver.example.com",
                                                 "-ccheck_disk1",
                                                 "-p5666"],
                                                stdout=-1,
                                                universal_newlines=True)

    @patch('syslog.syslog')
    @patch('mownitoring.check_notifier')
    @patch('mownitoring.notify_syslog')
    def test_check_status(self, mock_syslog, mock_check_notifier,
                          mock_notify_syslog):
        mownitoring.check_nrpe = Mock()
        mownitoring.check_nrpe.return_value = 2, 'disk nok'
        mock_check_notifier.return_value = [mownitoring.notify_syslog]
        mownitoring.check_status("disk1", "webserver.example.com", "5666",
                                 "webserver.example.com", ["syslog"])
        mock_syslog.assert_called_once_with("webserver.example.com!" +
                                            "disk1 disk nok")

    @patch('smtplib.SMTP')
    @patch('email.mime.text.MIMEText')
    def test_notify_mail(self, mock_mimetext, mock_smtp):
        # we need api_cfg
        mownitoring.read_conf(config_file)
        test_body = (
            "Hi,\n",
            "We detected a problem:\n",
            "webserver.example.com!disk1 disk nok",
            "Yours truly,\n",
            "Mownitoring"
        )
        mownitoring.notify_mail("webserver.example.com!disk1 disk nok")
        mock_mimetext.assert_called_once_with(str(test_body))


if __name__ == '__main__':
    unittest.main()
