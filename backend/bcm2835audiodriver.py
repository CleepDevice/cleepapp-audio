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
        self.modprobe = Modprobe()
        self.console = Console()

    #def _set_card_id(self):
    #    """
    #    Set card id
    #    """
    #    for card_id, card in self.alsa.get_playback_devices().items():
    #        if card[u'name'].find(u'bcm2835')>=0:
    #            self.card_id = card_id
    #            break

    def get_device_infos(self):
        """
        Returns device infos

        Returns:
            dict: device infos::

                {
                    cardname (string): card name
                    cardid (int): card id
                    deviceid (int): device id
                    playback (bool): True if device can play audio
                    capture (bool): True if device can record audio
                }

        """
        return {
            u'cardname': self.CARD_NAME,
            u'playback': True,
            u'capture': False,
        }

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

        #also register system module
        self.register_system_modules([self.MODULE_NAME])

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

        #also unregister system module
        self.unregister_system_modules([self.MODULE_NAME])

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
        #clean previous alsa conf
        self.asoundconf.delete()

        #enable system module
        if not self.modprobe.load_module(self.MODULE_NAME):
            self.logger.error(u'Unable to load system module "%s"' % self.MODULE_NAME)
            return False

        #create default /etc/asound.conf
        #self.logger.debug(u'Write to /etc/asound.conf values "%s:%s"' % (self.card_id, self.device_id))
        #if not self.asoundconf.set_default_device(self.card_id, self.device_id):
        #    self.logger.error(u'Unable to create /etc/asound.conf for soundcard "%s"' % self.CARD_NAME)
        #    return False

        #configure default (jack) in alsa
        if not self.alsa.amixer_control(Alsa.CSET, 3, 1):
            self.logger.error(u'Error executing amixer command')
            return False

        #force saving alsa conf
        self.alsa.save()

        return True

    def disable(self, params=None):
        """
        Disable driver

        Args:
            params (dict): additional parameters
        """
        #configure alsa
        #if not self.alsa.amixer_control(Alsa.CSET, 3, 0):
        #    self.logger.error(u'Error executing amixer command')
        #    return False

        if not self.asoundconf.delete():
            self.logger.error(u'Unable to delete asound.conf file')
            return False

        self.logger.debug(u'Unloading system module "%s"' % self.MODULE_NAME)
        if not self.modprobe.unload_module(self.MODULE_NAME):
            self.logger.error(u'Unable to unload system module "%s"' % self.MODULE_NAME)
            return False

        return True

    def is_enabled(self):
        """
        Returns True if driver is enabled

        Returns:
            bool: True if enable
        """
        selected_device = self.alsa.get_selected_device()
        if selected_device and selected_device[u'name']==self.CARD_NAME:
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

