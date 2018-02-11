#!/usr/bin/env python3

import unittest
import mownitoring

config_file = "./mownitoring.yml"


class TestMownitoing(unittest.TestCase):

    def test_readconf(self):
        machines = mownitoring.readconf(config_file)

        # api_cfg
        self.assertEqual(mownitoring.api_cfg["twilio_api_url"],
                         "https://api.twilio.com/2010-04-01/Accounts/" +
                         mownitoring.api_cfg["twilio_account_sid"] +
                         "/Messages")
        self.assertEqual(mownitoring.api_cfg["pushover_token"],
                         "T0k3n")

        # machines
        self.assertIsInstance(machines["webserver.example.com"][0]["checks"],
                              list)
        self.assertEqual(machines["db.example.com"][2]["connection"]["ip"],
                         "192.0.2.2")
        self.assertIn("mailq", machines["mail.example.com"][0]["checks"])

        self.assertIn("twilio", machines["mail.example.com"][1]["alert"])

        self.assertNotIn("twilio_auth_token", machines)
        self.assertNotIn("pushover_token", machines)


if __name__ == '__main__':
    unittest.main()
