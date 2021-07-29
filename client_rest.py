#!/usr/bin/env python3
"""
Copyright (c) 2018, Patrick Salecker
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice,
      this list of conditions and the following disclaimer in
      the documentation and/or other materials provided with the distribution.
    * Neither the name of the author nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""

import threading
import time
import requests

try:
    # since Kismet 2019-05-R1
    import kismet_rest as KismetRest
except ModuleNotFoundError:
    # up to Kismet 2019-04-R1
    import KismetRest

class RestClient:
    def __init__(self, logger):
        self.logger = logger
        self.debug = False
        self.uri = "http://127.0.0.1:2501"
        self.connector = None
        self.connected = False
        self.authenticated = False
        self.credentials = None
        self.timestamp = {
            'devices': 0,
            'messages': 0,
        }
        self.queue = {}
        self.empty_queue()
        self.error = []

    def empty_queue(self):
        self.queue = {
            'dot11': [],
            'status': None,
            'location': [],
            'messages': [],
            'datasources': {},
        }

    def start(self):
        """Open connection to the server
        """
        self.logger.info("Клиент: запуск %s" % self.uri)

        if not self._simple_server_check():
            self.connected = False
            return False

        sessioncache_path = "~/.kismon/kismet-session-%s" % ''.join(e if e.isalnum() else '-' for e in self.uri)
        self.connector = KismetRest.KismetConnector(self.uri, sessioncache_path=sessioncache_path)
        self.authenticate()
        if not self.update_system_status():
            return False
        self.connected = True

    def stop(self):
        """Close connection to the server
        """
        self.logger.info("Клиент: остановка %s" % self.uri)
        self.connected = False

    def _simple_server_check(self):
        error_str = '%s не доступен или не правильно введён адрес \nОшибка: %s'
        try:
            response = requests.get("%s/system/timestamp.json" % (self.uri))
        except requests.exceptions.RequestException as e:
            if 'reason' in dir(e.args[0]):
                message = error_str % (self.uri, e.args[0].reason)
            else:
                message = error_str % (self.uri, e.args[0])
            self.logger.error(message)
            self.error.append(message)
            return False
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            return True
        else:
            self.logger.error(error_str % (self.uri, response.text))
            self.error.append(error_str % (self.uri, response.text))
            return False

    def _callback(self, device):
        # print(device['dot11.device']['dot11.device.last_beaconed_ssid'])
        self.queue['dot11'].append(device)

    def get_updated_devices(self, queue_list=None):
        fields = [
            'dot11.device',
            'kismet.device.base.channel',
            'kismet.device.base.crypt',
            'kismet.device.base.first_time',
            'kismet.device.base.key',
            'kismet.device.base.last_time',
            'kismet.device.base.location',
            'kismet.device.base.macaddr',
            'kismet.device.base.manuf',
            'kismet.device.base.seenby',
            'kismet.device.base.signal/kismet.common.signal.last_signal',
            'kismet.device.base.signal/kismet.common.signal.min_signal',
            'kismet.device.base.signal/kismet.common.signal.max_signal',
            'kismet.device.base.signal/kismet.common.signal.type',
        ]
        if queue_list:
            self.queue = queue_list

        new_timestamp = time.time()
        time_diff = int(self.timestamp['devices'] - new_timestamp - 1)
        self.connector.smart_device_list(callback=self._callback, fields=fields, ts=time_diff)
        self.timestamp['devices'] = new_timestamp

    def loop(self):
        while self.connected is True:
            self.get_updated_devices()
            self.update_system_status()
            self.update_location()
            self.queue_new_messages()
            self.update_datasources()
            for name in self.queue:
                print("'%s': " % name, self.queue[name])
            self.empty_queue()
            time.sleep(1)

    def update_system_status(self):
        try:
            status = self.connector.system_status()
        except Exception as e:
            self.connected = False
            self.logger.error("Клиент: ошибка подключения")
            self.logger.error(e)
            self.error.append("Ошибка подключение: %s" % e)
            return False
        self.queue['status'] = status
        return True

    def update_location(self):
        if not self.authenticated:
            return False
        self.queue['location'].append(self.connector.location())

    def queue_new_messages(self):
        messages = self.connector.messages(ts_sec=self.timestamp['messages'])
        self.timestamp['messages'] = int(time.time())
        self.queue['messages'].extend(messages['kismet.messagebus.list'])

    def update_datasources(self):
        self.queue['datasources'] = self.connector.datasources()

    def get_available_datasources(self):
        if not self.authenticated:
            if not self.authenticate():
                return False

        datasources = self.connector.datasource_list_interfaces()
        return datasources

    def add_datasource(self, interface):
        response = self.connector.add_datasource(interface)
        self.logger.debug(response)

    def authenticate(self):
        self.logger.info("авторизация...")
        if not self.credentials:
            self.logger.debug('нет записей')
            return False

        self.connector.set_login(self.credentials[0], self.credentials[1])
        response = self.connector.login()
        if response == False:
            self.authenticated = False
            self.logger.info("Ошибка авторизации")
            return False
        self.authenticated = True
        self.logger.info("Успешная авторизация")
        return True

    def set_channel(self, uuid, mode, value):
        self.logger.debug('set_channel %s %s %s' % (uuid, mode, value))
        if not self.connected:
            self.logger.debug('нет подключения')
            return False

        if not self.authenticated:
            if not self.authenticate():
                return False

        if mode == 'lock':
            self.connector.config_datasource_set_channel(uuid=uuid, channel=str(value))
        elif mode == 'hop':
            self.connector.config_datasource_set_hop_rate(uuid=uuid, rate=value)


class RestClientThread(threading.Thread):
    def __init__(self, logger, uri=None):
        threading.Thread.__init__(self)
        self.logger = logger
        self.debug = False
        self.client = RestClient(logger=logger)
        self.is_running = False
        if uri is not None:
            self.client.uri = uri

    def stop(self):
        self.is_running = None
        if self.client.connected is True:
            self.client.stop()

    def get_queue(self, name):
        try:
            return self.client.queue[name]
        except KeyError:
            self.logger.debug("очередь %s отсутствует" % name)
            return False

    def run(self):
        self.is_running = True
        self.client.error = []
        if self.client.start() is False:
            self.stop()
        while self.is_running is True and (self.client.connected is True):
            # try:
            self.client.get_updated_devices()
            self.client.update_system_status()
            self.client.update_location()
            self.client.queue_new_messages()
            self.client.update_datasources()
            # print(self.client.queue)
            time.sleep(1)
        self.stop()


def get_crypt_list():
    """see packet_ieee80211.h from kismet-newcore
    """
    cryptsets = ["none", "unknown", "wep", "layer3 ", "wep40", "wep104",
                 "tkip", "wpa", "psk", "aes_ocb", "aes_ccm", "leap", "ttls",
                 "peap", "pptp", "fortress", "keyguard", "unknown_nonwep",
                 "wpa_migmode", "version_wpa", "version_wpa2"]

    return cryptsets


def encode_cryptset(crypts):
    cryptsets = get_crypt_list()
    bin_cryptset = []
    for crypt in cryptsets:
        if crypt in crypts:
            bit = "1"
        else:
            bit = "0"
        bin_cryptset.insert(0, bit)
    cryptset = int("".join(bin_cryptset[:-1]), 2)
    return cryptset


def decode_cryptset(cryptset, return_str=False):
    cryptsets = get_crypt_list()
    if cryptset == 0:
        if return_str is True:
            return cryptsets[cryptset]
        else:
            return [cryptsets[cryptset]]

    crypts = []
    pos = 1
    bin_cryptset = bin(cryptset)[2:][::-1]
    for bit in bin_cryptset:
        if bit == "1":
            try:
                crypts.append(cryptsets[pos])
            except IndexError:
                pass
        pos += 1

    if return_str is True:
        return ",".join(crypts).upper()
    else:
        return crypts


def decode_network_typeset(num):
    """see phy_80211.h from kismet
    """
    bits = "{0:b}".format(int(num + 1))
    type_bits = ['unknown', 'beakon_ap', 'adhoc', 'client', 'wds', 'turbocell', 'inferred_wireless', 'inferred_wired',
                 'probe_ap']

    flags = []
    position = len(bits) - 1
    for bit in bits:
        if bit == "1":
            flags.append(type_bits[position])
        position -= 1

    if 'beakon_ap' in flags or 'probe_ap' in flags:
        return 'infrastructure'
    elif 'client' in flags:
        return 'client'
    elif 'adhoc' in flags:
        return 'ad-hoc'
    elif 'unknown' in flags and len(flags) == 1:
        return 'unknown'
    else:
        print("Неизвестный тип")
        print(num, "vs.", bits)
        print(flags)
        return 'unknown'


if __name__ == "__main__":
    client = RestClient()
    client.debug = True
    client.start()
    try:
        client.loop()
    except KeyboardInterrupt:
        client.stop()
    print("конец")
