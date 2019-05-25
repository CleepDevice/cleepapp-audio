#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import os
from raspiot.utils import InvalidParameter, MissingParameter
from raspiot.libs.commands.alsa import Alsa
from raspiot.libs.commands.modprobe import Modprobe
from raspiot.libs.configs.etcasoundconf import EtcAsoundConf
from raspiot.libs.drivers.audiodriver import AudioDriver
from raspiot.libs.internals.console import Console
from raspiot.libs.configs.configtxt import ConfigTxt
import raspiot.libs.internals.tools as Tools

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

    AMIXER_AUTO = 0
    AMIXER_JACK = 1
    AMIXER_HDMI = 2

    def __init__(self, cleep_filesystem):
        """
        Constructor

        Args:
            cleep_filesystem (CleepFilesystem): CleepFilesystem instance
        """
        #init
        AudioDriver.__init__(self, cleep_filesystem, u'Raspberry pi soundcard', self.CARD_NAME)

        #members
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        self.alsa = Alsa(self.cleep_filesystem)
        self.asoundconf = EtcAsoundConf(self.cleep_filesystem)
        self.configtxt = ConfigTxt(self.cleep_filesystem)
        #self.modprobe = Modprobe()
        self.console = Console()

    def _get_card_name(self):
        """
        Return card name

        Returns:
            string: card name
        """
        return self.CARD_NAME

    def _get_card_capabilities(self):
        """
        Return card capabilities

        Returns:
            tuple: card capabilities::

                (
                    bool: playback capability,
                    bool: capture capability
                )
        """
        return (True, False)

    def _install(self, params=None):
        """
        Install driver

        Args:
            params (dict): additional parameters
        """
        if not Tools.raspberry_pi_infos()[u'audio']:
            raise Exception(u'Raspberry pi has no onboard audio device')

        #installing native audio device consists of enabling dtparam audio in /boot/config.txt
        if not self.configtxt.enable_audio():
            raise Exception(u'Error enabling audio in /boot/config.txt')

        return True

    def _uninstall(self, params=None):
        """
        Uninstall driver

        Args:
            params (dict): additional parameters
        """
        if not Tools.raspberry_pi_infos()[u'audio']:
            raise Exception(u'Raspberry pi has no onboard audio device')

        #uninstalling native audio device consists of disabling dtparam audio in /boot/config.txt
        if not self.configtxt.disable_audio():
            raise Exception(u'Error disabling audio in /boot/config.txt')

        return True
            
    def is_installed(self):
        """
        Is driver installed

        Returns:
            bool: True if driver is installed
        """
        return self.configtxt.is_audio_enabled()

    def enable(self, params=None):
        """
        Enable driver
        """
        #create default /etc/asound.conf
        card_infos = self._get_cardid_deviceid()
        self.logger.debug(u'card_infos=%s' % str(card_infos))
        if card_infos[0] is None:
            self.logger.error(u'Unable to get alsa infos for card "%s"' % self.CARD_NAME)
            return False
        self.logger.debug(u'Write to /etc/asound.conf values "%s:%s"' % (card_infos[0], card_infos[1]))
        if not self.asoundconf.save_default_file(card_infos[0], card_infos[1]):
            self.logger.error(u'Unable to create /etc/asound.conf for soundcard "%s"' % self.CARD_NAME)
            return False

        #configure default output to "auto" in alsa (0=auto, 1=headphone jack, 2=HDMI)
        if not self.alsa.amixer_control(Alsa.CSET, 3, self.AMIXER_JACK):
            self.logger.error(u'Error executing amixer command')
            return False

        #force saving alsa conf (this will create asound.state if needed)
        self.alsa.save()

        return True

    def disable(self, params=None):
        """
        Disable driver

        Args:
            params (dict): additional parameters
        """
        #configure alsa to "auto"
        self.logger.debug(u'Configure alsa')
        if not self.alsa.amixer_control(Alsa.CSET, 3, self.AMIXER_AUTO):
            self.logger.error(u'Error executing amixer command')
            return False

        self.logger.debug(u'Delete /etc/asound.conf and /var/lib/alsa/asound.state')
        if not self.asoundconf.delete():
            self.logger.error(u'Unable to delete asound.conf file')
            return False

        self.logger.debug(u'Driver disabled')
        return True

    def is_enabled(self):
        """
        Is driver enabled ?

        Returns:
            bool: True if driver enabled
        """
        card = self._is_card_enabled(self.CARD_NAME)
        asound = self.asoundconf.exists()
        
        return card and asound

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

        Returns:
            dict: volumes level::

                {
                    playback (float): playback volume
                    capture (float): capture volume
                }

        """
        return {
            u'playback': self.alsa.set_volume(self.VOLUME_CONTROL, self.VOLUME_PATTERN, playback),
            u'capture': None
        }

