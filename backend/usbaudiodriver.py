#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from cleep.libs.configs.etcasoundconf import EtcAsoundConf
from cleep.libs.drivers.audiodriver import AudioDriver
from cleep.libs.internals.console import Console
from cleep.libs.configs.configtxt import ConfigTxt


class UsbAudioDriver(AudioDriver):
    """
    Audio driver for USB audio devices

    Tested hardare:
     * Mini external USB stereo speaker: https://thepihut.com/collections/raspberry-pi-usb-audio/products/mini-external-usb-stereo-speaker
    """

    VOLUME_PATTERN = ("Mono", r"\[(\d*)%\]")

    def __init__(self):
        """
        Constructor
        """
        AudioDriver.__init__(self, "USB audio device")

        self.asoundconf = None
        self.configtxt = None
        self.console = None
        self.volume_control = ""
        self.volume_control_numid = None

    def _on_audio_registered(self):
        """
        Audio driver registered
        """
        self.asoundconf = EtcAsoundConf(self.cleep_filesystem)
        self.configtxt = ConfigTxt(self.cleep_filesystem)
        self.console = Console()

    def _get_card_name(self, devices_names):
        """
        Return card name

        Returns:
            string: card name or None if card not found
        """
        pattern = re.compile("usb", re.IGNORECASE)
        for device_name in devices_names:
            if pattern.match(device_name["device_desc"]):
                return device_name["card_name"]

        return None

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
        # as the default driver and just in case, delete existing config
        self.asoundconf.delete()

        # install pulseaudio debian package
        resp = self.console.command(
            "apt update -qq && apt install -q --yes pulseaudio", timeout=300
        )
        if resp["returncode"] != 0:
            self.logger.error("Unable to install USB audio: %s", resp)
            return False

        # installing native audio device consists of enabling dtparam audio in /boot/config.txt
        if not self.configtxt.enable_audio():
            raise Exception("Error enabling USB audio")

        return True

    def _uninstall(self, params=None):
        """
        Uninstall driver

        Args:
            params (dict): additional parameters
        """
        resp = self.console.command("apt purge --q --yes pulseaudio")
        if resp["returncode"] != 0:
            self.logger.error("Unable to uninstall USB audio: %s", resp)
            raise Exception('Unable to uninstall USB audio')

        return True

    def is_installed(self):
        """
        Is driver installed

        Returns:
            bool: True if driver is installed
        """
        resp = self.console.command("dpkg -s pulseaudio")
        return resp["returncode"] == 0

    def enable(self, params=None):
        """
        Enable driver
        """
        if not self.get_card_name():
            raise Exception("No USB audio found. Please connect it before enabling it")

        # as the default driver and just in case, delete existing config
        self.asoundconf.delete()

        # create default /etc/asound.conf
        card_infos = self.get_cardid_deviceid()
        self.logger.debug("card_infos=%s", card_infos)
        if card_infos[0] is None:
            self.logger.error(
                'Unable to get alsa infos for card "%s"', self.get_card_name()
            )
            return False
        self.logger.debug(
            'Write to /etc/asound.conf values "%s:%s"', card_infos[0], card_infos[1]
        )
        if not self.asoundconf.save_default_file(card_infos[0], card_infos[1]):
            self.logger.error(
                'Unable to create /etc/asound.conf for soundcard "%s"',
                self.get_card_name(),
            )
            return False

        # force saving alsa conf (this will create asound.state if needed)
        self.alsa.save()

        return True

    def disable(self, params=None):
        """
        Disable driver

        Args:
            params (dict): additional parameters
        """
        self.logger.debug("Delete /etc/asound.conf and /var/lib/alsa/asound.state")
        if not self.asoundconf.delete():
            self.logger.error("Unable to delete asound.conf file")
            return False

        self.logger.debug("Driver disabled")
        return True

    def is_enabled(self):
        """
        Is driver enabled ?

        Returns:
            bool: True if driver enabled
        """
        card = self.is_card_enabled()
        asound = self.asoundconf.exists()

        return card and asound

    def _set_volumes_controls(self):
        """
        Set controls to control volumes
        """
        # search for appropriate volume control
        controls = self.alsa.get_simple_controls()
        self.volume_control = controls[0] if len(controls) > 0 else ""

        # get volume control numid
        self.volume_control_numid = self.get_control_numid("Volume")

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
            "playback": self.alsa.get_volume(self.volume_control, self.VOLUME_PATTERN),
            "capture": None,
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
            "playback": self.alsa.set_volume(
                self.volume_control, self.VOLUME_PATTERN, playback
            ),
            "capture": None,
        }

    def require_reboot(self):
        """
        Require reboot after install/uninstall

        Returns:
            bool: True if reboot required
        """
        return False
