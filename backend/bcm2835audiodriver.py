#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import os
from raspiot.utils import InvalidParameter, MissingParameter
from raspiot.libs.commands.alsa import Alsa
from raspiot.libs.configs.etcasoundconf import EtcAsoundConf
from raspiot.libs.drivers.audiodriver import AudioDriver
from raspiot.libs.internals.console import Console

class Bcm2835AudioDriver(AudioDriver):
    """
    Audio driver for BCM2835 device (embedded raspberrypi soundcard)

    Note:
        https://www.raspberrypi.org/documentation/configuration/audio-config.md
    """

    MODULE_NAME = u'snd_bcm2835'
    CARD_NAME = u'bcm2835 ALSA'

    VOLUME_CONTROL = u'PCM'
    VOLUME_PATTERN = (u'Mono', r'\[(\d*)%\]')

    AMIXER_JACK = 1
    AMIXER_HDMI = 2

    def __init__(self, cleep_filesystem, driver_name):
        """
        Constructor

        Args:
            cleep_filesystem (CleepFilesystem): CleepFilesystem instance
            driver_name (string): driver name
        """
        #init
        AudioDriver.__init__(self, cleep_filesystem, driver_name)

        #members
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        self.alsa = Alsa()
        self.asoundconf = EtcAsoundConf(self.cleep_filesystem)
        self.console = Console()
        self.card_id = None
        self.device_id = 0

        #set card id
        self._set_card_id()

    def _set_card_id(self):
        """
        Set card id
        """
        for card_id, card in self.alsa.get_playback_devices().items():
            if card[u'name'].find(u'bcm2835')>=0:
                self.card_id = card_id
                break

    def get_device_infos(self):
        """
        Returns device infos

        Returns:
            dict: device infos::

                {
                    cardname (string): card name
                    cardid (int): card id
                    deviceid (int): device id
                }

        """
        return {
            u'cardname': self.CARD_NAME,
            u'cardid': self.card_id,
            u'deviceid': self.device_id,
        }

    def install(self, params=None):
        """
        Install driver

        Args:
            params (dict): additional parameters
        """
        #system module, everything should be already installed
        pass

    def uninstall(self, params=None):
        """
        Uninstall driver

        Args:
            params (dict): additional parameters
        """
        #system module, nothing to uninstall
        pass

    def is_installed(self):
        """
        Is driver installed

        Returns:
            bool: True if driver is installed
        """
        return self.lsmod.is_module_loaded(self.MODULE_NAME)

    def enable(self, params=None):
        """
        Enable driver
        """
        cmd = u'/usr/bin/amixer cset numid=3 1'
        self.logger.debug(u'Enable cmd: %s' % cmd)
        self.console.command(cmd)

        self.logger.debug(u'Write to /etc/asound.conf values "%s:%s"' % (self.card_id, self.device_id))
        return self.asoundconf.set_default_device(self.card_id, self.device_id)

    def disable(self, params=None):
        """
        Disable driver

        Args:
            params (dict): additional parameters
        """
        cmd = u'/usr/bin/amixer cset numid=3 0'
        self.logger.debug(u'Disable cmd: %s' % cmd)
        self.console.command(cmd)

        return self.asoundconf.delete()

    def is_enabled(self):
        """
        Returns True if driver is enabled

        Returns:
            bool: True if enable
        """
        selected_device = self.alsa.get_selected_device()
        if selected_device and selected_device[u'cardid']==self.card_id and selected_device[u'deviceid']==self.device_id:
            return True
            
        return False

    def get_volumes(self):
        """
        Get volumes

        Returns:
            dict: volumes level::

                {
                    playback (float): playback volume
                    capture (float): capture volume
                }

        """
        return {
            u'playback': self.alsa.get_volume(self.VOLUME_CONTROL, self.VOLUME_PATTERN),
            u'capture': None
        }

    def set_volumes(self, playback=None, capture=None):
        """
        Set volumes

        Args:
            playback (float): playback volume (None to disable update)
            capture (float): capture volume (None to disable update)
        """
        return {
            u'playback': self.alsa.set_volume(self.VOLUME_CONTROL, self.VOLUME_PATTERN, playback),
            u'capture': None
        }

