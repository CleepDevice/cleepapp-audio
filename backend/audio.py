#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
from cleep.core import CleepResources
from cleep.exception import CommandError, InvalidParameter
from cleep.libs.commands.alsa import Alsa
from cleep.libs.configs.etcasoundconf import EtcAsoundConf
from cleep.libs.drivers.driver import Driver
import cleep.libs.internals.tools as Tools
from .bcm2835audiodriver import Bcm2835AudioDriver
from .usbaudiodriver import UsbAudioDriver

__all__ = ["Audio"]


class Audio(CleepResources):
    """
    Audio module is in charge of configuring audio on raspberry pi
    """

    MODULE_AUTHOR = "Cleep"
    MODULE_VERSION = "2.1.0"
    MODULE_CATEGORY = "APPLICATION"
    MODULE_DEPS = []
    MODULE_DESCRIPTION = "Configure audio on your device"
    MODULE_LONGDESCRIPTION = (
        "Application that helps you to configure audio on your device"
    )
    MODULE_TAGS = ["audio", "sound"]
    MODULE_URLINFO = "https://github.com/tangb/cleepmod-audio"
    MODULE_URLHELP = "https://github.com/tangb/cleepmod-audio/wiki"
    MODULE_URLBUGS = "https://github.com/tangb/cleepmod-audio/issues"
    MODULE_URLSITE = None

    MODULE_CONFIG_FILE = "audio.conf"
    DEFAULT_CONFIG = {"driver": None}

    TEST_SOUND = "connected.wav"

    MODULE_RESOURCES = {
        "audio.playback": {
            "permanent": False,
        },
        "audio.capture": {
            "permanent": False,
        },
    }

    def __init__(self, bootstrap, debug_enabled):
        """
        Constructor

        Args:
            bootstrap (dict): bootstrap objects
            debug_enabled (bool): flag to set debug level to logger
        """
        # init
        CleepResources.__init__(self, bootstrap, debug_enabled)

        # members
        self.alsa = Alsa(self.cleep_filesystem)
        self.asoundconf = EtcAsoundConf(self.cleep_filesystem)
        self.bcm2835_driver = Bcm2835AudioDriver()
        self.usb_driver = UsbAudioDriver()

        # register default audio drivers
        self._register_driver(self.bcm2835_driver)
        self._register_driver(self.usb_driver)

    def _configure(self):
        """
        Module configuration
        """
        # restore selected soundcard
        selected_driver_name = self._get_config_field("driver")
        self.logger.trace(
            "selected_driver_name=%s audio supported=%s",
            selected_driver_name,
            Tools.raspberry_pi_infos()["audio"],
        )
        if not selected_driver_name and Tools.raspberry_pi_infos()["audio"]:
            # set default sound driver to raspberry pi embedded one
            self.logger.trace("Set default sound driver")
            selected_driver_name = self.bcm2835_driver.name
            self._set_config_field("driver", self.bcm2835_driver.name)

        if selected_driver_name is None:
            # still no selected driver name, it means audio is not supported on this board
            self.logger.info("No audio supported on this device")
            return
        self.logger.info('Selected audio driver "%s"', selected_driver_name)

        # get selected driver
        driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, selected_driver_name)

        # fallback to default driver if necessary (and possible)
        if not driver and Tools.raspberry_pi_infos()["audio"]:
            self.logger.warning(
                "Configured audio driver is not loaded, fallback to default one."
            )
            self._set_config_field("driver", self.bcm2835_driver.name)
            driver = self.drivers.get_driver(
                Driver.DRIVER_AUDIO, self.bcm2835_driver.name
            )

        # enable driver if possible
        if not driver:
            self.logger.info("No audio driver found while it should be")
            return
        if not driver.is_installed():
            self.logger.error(
                "Unable to enable soundcard because it is not properly installed. Please reinstall it."
            )
        elif not driver.is_enabled():
            self.logger.info('Enabling audio driver "%s"', driver.name)
            if not driver.enable():
                self.logger.error("Unable to enable audio. Internal driver error.")
        else:
            self.logger.debug("Audio driver seems to be already configured")

    def get_module_config(self):
        """
        Return module configuration

        Returns:
            dict: audio config::

                {
                    volumes (dict): volumes values (playback and capture)
                    devices (dict): audio devices installed on device (playback and capture)
                }

        """
        playbacks = []
        captures = []
        volumes = {
            "playback": None,
            "capture": None,
        }

        audio_drivers = self.drivers.get_drivers(Driver.DRIVER_AUDIO)
        for driver_name, driver in audio_drivers.items():
            try:
                device_infos = driver.get_device_infos()
                device = {
                    "name": driver.get_card_name(),
                    "label": driver_name,
                    "device": device_infos,
                    "enabled": driver.is_enabled(),
                    "installed": driver.is_installed(),
                }
                if device_infos["playback"]:
                    playbacks.append(device)
                if device_infos["capture"]:
                    captures.append(device)
                if device["enabled"] and device["installed"]:
                    volumes = driver.get_volumes()
            except Exception as error:
                # problem with driver, unregister it
                self.logger.warn(
                    'Audio driver "%s" disabled due to error: %s', driver_name, str(error)
                )
                self.drivers.unregister(driver)

        return {
            "devices": {
                "playback": sorted(playbacks, key=lambda k: k["label"]),
                "capture": sorted(captures, key=lambda k: k["label"]),
            },
            "volumes": volumes,
        }

    def select_device(self, driver_name):
        """
        Select audio device

        Args:
            driver_name (string): driver name

        Returns:
            bool: True if device saved successfully

        Raises:
            InvalidParameter: if parameter is invalid
        """
        # check params
        self._check_parameters(
            [
                {"name": "driver_name", "type": str, "value": driver_name},
                {
                    "name": "driver_name",
                    "type": str,
                    "value": driver_name,
                    "validator": lambda val: driver_name
                    != self._get_config_field("driver"),
                    "message": f'Device "{driver_name}" is already selected',
                },
            ]
        )

        # get drivers
        selected_driver_name = self._get_config_field("driver")
        old_driver = (
            self.drivers.get_driver(Driver.DRIVER_AUDIO, selected_driver_name)
            if selected_driver_name is not None
            else None
        )
        new_driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, driver_name)

        if not new_driver:
            raise InvalidParameter("Specified driver does not exist")
        if not new_driver.is_installed():
            raise InvalidParameter(
                "Can't selected device because its driver seems not to be installed"
            )

        # disable old driver
        self.logger.info('Using audio driver "%s"', new_driver.name)
        if old_driver and old_driver.is_installed():
            disabled = old_driver.disable()
            self.logger.debug(
                'Disable previous driver "%s": %s', old_driver.name, disabled
            )
            if not disabled:
                raise CommandError("Unable to disable current driver")

        # enable new driver
        self.logger.debug('Enable new driver "%s"', new_driver.name)
        driver_enabled = new_driver.enable()
        if not driver_enabled or not new_driver.is_card_enabled():
            self.logger.info(
                "Unable to enable selected driver. Revert re-enabling previous driver"
            )
            if old_driver:
                old_driver.enable()
            raise CommandError("Unable to enable selected device")

        # everything is fine, save new driver
        self._set_config_field("driver", new_driver.name)

        # restart cleep
        self.send_command("restart_cleep", "system")

    def set_volumes(self, playback, capture):
        """
        Update volume

        Args:
            playback (int): playback volume percentage
            capture (int): capture volume percentage

        Returns:
            dict: current volume::

                {
                    playback (int)
                    capture (int)
                }

        Raises:
            InvalidParameters if parameter is invalid
        """
        self._check_parameters(
            [
                {"name": "playback", "type": int, "value": playback, "none": True},
                {
                    "name": "playback",
                    "type": int,
                    "value": playback,
                    "validator": lambda val: 0 <= val <= 100,
                    "message": 'Parameter "playback" must be 0<=playback<=100',
                },
                {"name": "capture", "type": int, "value": capture, "none": True},
                {
                    "name": "capture",
                    "type": int,
                    "value": capture,
                    "validator": lambda val: 0 <= val <= 100,
                    "message": 'Parameter "capture" must be 0<=capture<=100',
                },
            ]
        )

        self.logger.info(
            "Set volumes to: playback[%s%%] capture[%s%%]", playback, capture
        )

        selected_driver_name = self._get_config_field("driver")
        volumes = {
            "playback": None,
            "capture": None,
        }

        # no driver configured
        if not selected_driver_name:
            self.logger.debug("No driver configured, return no volumes")
            return volumes

        driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, selected_driver_name)
        # no driver found
        if not driver:
            self.logger.warning('Driver "%s" not found', selected_driver_name)
            return volumes

        # set volumes
        driver.set_volumes(playback, capture)

        return driver.get_volumes()

    def test_playing(self):
        """
        Play test sound to make sure audio card is correctly configured
        """
        # request playback resource
        self._need_resource("audio.playback")

    def test_recording(self):
        """
        Record sound during few seconds and play it
        """
        # request capture resource (non blocking)
        self._need_resource("audio.capture")

        # pause to simulate 5 seconds recording
        time.sleep(5.0)

    def _resource_acquired(self, resource_name):
        """
        Function called when resource is acquired

        Args:
            resource_name (string): acquired resource name

        Raises:
            CommandError: if command failed
        """
        self.logger.debug('Resource "%s" acquired', resource_name)
        if resource_name == "audio.playback":
            # play test sample
            audio_path = os.path.join(self.APP_ASSET_PATH, self.TEST_SOUND)
            if not self.alsa.play_sound(audio_path):
                raise CommandError("Unable to play test sound: internal error")

            # release resource
            self._release_resource("audio.playback")

        elif resource_name == "audio.capture":
            # record sound
            sound = self.alsa.record_sound(timeout=5.0)
            self.logger.debug("Recorded sound: %s", sound)
            if not self.alsa.play_sound(sound, timeout=6.0):
                raise CommandError("Unable to play recorded sound: internal error")

            # release resource
            self._release_resource("audio.capture")

            # purge file
            time.sleep(0.5)
            try:
                os.remove(sound)
            except Exception:
                self.logger.warning('Unable to delete recorded test sound "%s"', sound)

        else:
            self.logger.error('Unsupported resource "%s" acquired', resource_name)

    def _resource_needs_to_be_released(self, resource_name):  # pragma: no cover
        """
        Function called when resource is acquired by other module and needs to be released.

        Args:
            resource_name (string): acquired resource name
        """
        # resource is not acquired for too long, it will be released naturally so nothing to do here
