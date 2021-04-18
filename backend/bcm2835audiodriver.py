#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from cleep.libs.commands.alsa import Alsa
from cleep.libs.configs.etcasoundconf import EtcAsoundConf
from cleep.libs.drivers.audiodriver import AudioDriver
from cleep.libs.internals.console import Console
from cleep.libs.configs.configtxt import ConfigTxt
import cleep.libs.internals.tools as Tools

class Bcm2835AudioDriver(AudioDriver):
    """
    Audio driver for BCM2835 device (embedded raspberrypi soundcard)

    Note:
        https://www.raspberrypi.org/documentation/configuration/audio-config.md
    """

    MODULE_NAME = 'snd_bcm2835'
    CARD_NAME = 'BCM2835'

    VOLUME_PATTERN = ('Mono', r'\[(\d*)%\]')

    AMIXER_AUTO = 0
    AMIXER_JACK = 1
    AMIXER_HDMI = 2

    def __init__(self, params):
        """
        Constructor

        Args:
            params (dict): driver parameters. See Driver class
        """
        # init
        AudioDriver.__init__(self, params, 'Raspberry pi soundcard', self.CARD_NAME)

        # members
        self.asoundconf = EtcAsoundConf(self.cleep_filesystem)
        self.configtxt = ConfigTxt(self.cleep_filesystem)
        self.console = Console()
        self.card_name = ''
        self.volume_control = ''

    def get_card_name(self):
        """
        Return card name

        Returns:
            string: card name
        """
        return self.card_name

    def get_card_capabilities(self):
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
        if not Tools.raspberry_pi_infos()['audio']:
            raise Exception('Raspberry pi has no onboard audio device')

        # as the default driver and just in case, delete existing config
        self.asoundconf.delete()

        # installing native audio device consists of enabling dtparam audio in /boot/config.txt
        if not self.configtxt.enable_audio():
            raise Exception('Error enabling raspberry pi audio')

        return True

    def _uninstall(self, params=None):
        """
        Uninstall driver

        Args:
            params (dict): additional parameters
        """
        if not Tools.raspberry_pi_infos()['audio']:
            raise Exception('Raspberry pi has no onboard audio device')

        # uninstalling native audio device consists of disabling dtparam audio in /boot/config.txt
        if not self.configtxt.disable_audio():
            raise Exception('Error disabling raspberry pi audio')

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
        # search appropriate card name
        devices = self.alsa.get_playback_devices()
        for card_id, card in devices.items():
            if card['name'].find('bcm2835') >= 0:
                self.card_name = card['name']
                break

        # as the default driver and just in case, delete existing config
        self.asoundconf.delete()

        # create default /etc/asound.conf
        card_infos = self.get_cardid_deviceid()
        self.logger.trace('card_infos=%s' % str(card_infos))
        if card_infos[0] is None:
            self.logger.error('Unable to get alsa infos for card "%s"' % self.card_name)
            return False
        self.logger.debug('Write to /etc/asound.conf values "%s:%s"' % (card_infos[0], card_infos[1]))
        if not self.asoundconf.save_default_file(card_infos[0], card_infos[1]):
            self.logger.error('Unable to create /etc/asound.conf for soundcard "%s"' % self.card_name)
            return False

        # configure default output to "auto" in alsa (0=auto, 1=headphone jack, 2=HDMI) if necessary
        route_control_numid = self.get_control_numid('Route')
        self.logger.trace('route_control_numid=%s' % route_control_numid)
        if route_control_numid is not None:
            if not self.alsa.amixer_control(Alsa.CSET, route_control_numid, self.AMIXER_JACK):
                self.logger.error('Error executing amixer command')
                return False

        # force saving alsa conf (this will create asound.state if needed)
        self.alsa.save()

        # search for appropriate volume control
        controls = self.alsa.get_simple_controls()
        self.volume_control = controls[0] if len(controls) > 0 else ''

        # get volume control numid
        self.volume_control_numid = self.get_control_numid('Volume')

        return True

    def disable(self, params=None):
        """
        Disable driver

        Args:
            params (dict): additional parameters
        """
        # configure alsa to "auto"
        self.logger.debug('Configure alsa')
        if not self.alsa.amixer_control(Alsa.CSET, 3, self.AMIXER_AUTO):
            self.logger.error('Error executing amixer command')
            return False

        self.logger.debug('Delete /etc/asound.conf and /var/lib/alsa/asound.state')
        if not self.asoundconf.delete():
            self.logger.error('Unable to delete asound.conf file')
            return False

        self.logger.debug('Driver disabled')
        return True

    def is_enabled(self):
        """
        Is driver enabled ?

        Returns:
            bool: True if driver enabled
        """
        card = self.is_card_enabled(self.card_name)
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
            'playback': self.alsa.get_volume(self.volume_control, self.VOLUME_PATTERN),
            'capture': None
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
            'playback': self.alsa.set_volume(self.volume_control, self.VOLUME_PATTERN, playback),
            'capture': None
        }

