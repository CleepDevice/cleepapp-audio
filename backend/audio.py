#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
from cleep.core import CleepResources
from cleep.exception import CommandError, InvalidParameter, MissingParameter
from cleep.libs.commands.alsa import Alsa
from cleep.libs.configs.etcasoundconf import EtcAsoundConf
from cleep.libs.drivers.driver import Driver
import cleep.libs.internals.tools as Tools
from .bcm2835audiodriver import Bcm2835AudioDriver

__all__ = ['Audio']


class Audio(CleepResources):
    """
    Audio module is in charge of configuring audio on raspberry pi
    """
    MODULE_AUTHOR = u'Cleep'
    MODULE_VERSION = u'1.1.0'
    MODULE_CATEGORY = u'APPLICATION'
    MODULE_PRICE = 0
    MODULE_DEPS = []
    MODULE_DESCRIPTION = u'Configure audio on your device'
    MODULE_LONGDESCRIPTION = u'Application that helps you to configure audio on your device'
    MODULE_TAGS = [u'audio', u'sound']
    MODULE_COUNTRY = None
    MODULE_URLINFO = u'https://github.com/tangb/cleepmod-audio'
    MODULE_URLHELP = u'https://github.com/tangb/cleepmod-audio/wiki'
    MODULE_URLBUGS = u'https://github.com/tangb/cleepmod-audio/issues'
    MODULE_URLSITE = None

    MODULE_CONFIG_FILE = u'audio.conf'
    DEFAULT_CONFIG = {
        u'driver': None
    }

    TEST_SOUND = u'/opt/cleep/sounds/connected.wav'

    DEFAULT_DEVICE = {
        u'card': 0,
        u'device': 0
    }

    MODULE_RESOURCES = {
        u'audio.playback': {
            u'permanent': False,
        },
        u'audio.capture': {
            u'permanent': False,
        }
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
        self.bcm2835_driver = Bcm2835AudioDriver(self.cleep_filesystem)
        self.__cached_playback_devices = None
        self.__cached_capture_devices = None

        # register default audio drivers
        self._register_driver(self.bcm2835_driver)

    def _configure(self):
        """
        Module configuration
        """
        # restore selected soundcard
        selected_driver_name = self._get_config_field(u'driver')
        self.logger.trace('selected_driver_name=%s audio supported=%s' % (
            selected_driver_name,
            Tools.raspberry_pi_infos()[u'audio']
        ))
        if not selected_driver_name and Tools.raspberry_pi_infos()[u'audio']:
            # set default sound driver to raspberry pi embedded one
            self.logger.trace('Set default sound driver')
            selected_driver_name = self.bcm2835_driver.name
            self._set_config_field(u'driver', self.bcm2835_driver.name)

        if selected_driver_name is None:
            # still no selected driver name, it means audio is not supported on this board
            self.logger.info(u'No audio supported on this device')
            return
        self.logger.debug(u'Selected audio driver name "%s"' % selected_driver_name)

        # get selected driver
        driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, selected_driver_name)

        # fallback to default driver if necessary (and possible)
        if not driver and Tools.raspberry_pi_infos()[u'audio']:
            self.logger.warning('Configured audio driver is not loaded, fallback to default one.')
            self._set_config_field(u'driver', self.bcm2835_driver.name)
            driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, self.bcm2835_driver.name)

        # enable driver if possible
        if not driver:
            self.logger.info('No driver found while it should')
            return
        if not driver.is_installed():
            self.logger.error(u'Unable to enable soundcard because it is not properly installed. Please install it manually.')
        elif not driver.is_enabled():
            self.logger.info(u'Enabling audio driver "%s"' % driver.name)
            if not driver.enable():
                self.logger.error(u'Unable to enable soundcard. Internal driver error.')

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
            u'playback': None,
            u'capture': None,
        }

        audio_drivers = self.drivers.get_drivers(Driver.DRIVER_AUDIO)
        for driver_name, driver in audio_drivers.items():
            device_infos = driver.get_device_infos()
            device = {
                u'name': driver.card_name,
                u'label': driver_name,
                u'device': device_infos,
                u'enabled': driver.is_enabled(),
                u'installed': driver.is_installed(),
            }
            if device_infos[u'playback']:
                playbacks.append(device)
            if device_infos[u'capture']:
                captures.append(device)
            if device[u'enabled'] and device[u'installed']:
                volumes = driver.get_volumes()

        return {
            u'devices': {
                u'playback': sorted(playbacks, key=lambda k: k[u'label']),
                u'capture': sorted(captures, key=lambda k: k[u'label']),
            },
            u'volumes': volumes
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
        if driver_name is None or len(driver_name) == 0:
            raise MissingParameter(u'Parameter "driver_name" is missing')

        # get drivers
        selected_driver_name = self._get_config_field(u'driver')
        old_driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, selected_driver_name) if selected_driver_name is not None else None
        new_driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, driver_name)

        if not new_driver:
            raise InvalidParameter(u'Specified driver does not exist')
        if not new_driver.is_installed():
            raise InvalidParameter(u'Can\'t selected device because its driver seems not to be installed')

        # disable old driver
        self.logger.info(u'Using audio driver "%s"' % new_driver.name)
        if old_driver and old_driver.is_installed():
            disabled = old_driver.disable()
            self.logger.debug(u'Disable previous driver "%s": %s' % (old_driver.name, disabled))
            if not disabled:
                raise CommandError(u'Unable to disable current device')

        # enable new driver
        self.logger.debug(u'Enable new driver "%s"' % new_driver.name)
        driver_enabled = new_driver.enable()
        if not driver_enabled or not new_driver.is_card_enabled():
            self.logger.debug(u'Unable to enable new driver. Revert re-enabling old driver')
            if old_driver:
                old_driver.enable()
            raise CommandError(u'Unable to enable selected device')

        # everything is fine, save new driver
        self._set_config_field(u'driver', new_driver.name)

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
        if not isinstance(playback, int):
            raise InvalidParameter('Parameter "playback" has invalid type')
        if not isinstance(capture, int):
            raise InvalidParameter('Parameter "capture" has invalid type')
        if playback < 0 or playback > 100:
            raise InvalidParameter('Parameter "playback" must be a valid percentage')
        if capture < 0 or capture > 100:
            raise InvalidParameter('Parameter "capture" must be a valid percentage')

        self.logger.info(u'Set volumes to: playback[%s%%] capture[%s%%]' % (playback, capture))

        selected_driver_name = self._get_config_field(u'driver')
        volumes = {
            u'playback': None,
            u'capture': None,
        }

        # no driver configured
        if not selected_driver_name:
            self.logger.debug('No driver configured, return no volumes')
            return volumes

        driver = self.drivers.get_driver(Driver.DRIVER_AUDIO, selected_driver_name)
        # no driver found
        if not driver:
            self.logger.warning('Driver "%s" not found' % selected_driver_name)
            return volumes

        # set volumes
        driver.set_volumes(playback, capture)

        return driver.get_volumes()

    def test_playing(self):
        """
        Play test sound to make sure audio card is correctly configured
        """
        # request playback resource
        self._need_resource(u'audio.playback')

    def test_recording(self):
        """
        Record sound during few seconds and play it
        """
        # request capture resource (non blocking)
        self._need_resource(u'audio.capture')

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
        self.logger.debug('Resource "%s" acquired' % resource_name)
        if resource_name == u'audio.playback':
            # play test sample
            if not self.alsa.play_sound(self.TEST_SOUND):
                raise CommandError(u'Unable to play test sound: internal error')

            # release resource
            self._release_resource(u'audio.playback')

        elif resource_name == u'audio.capture':
            # record sound
            sound = self.alsa.record_sound(timeout=5.0)
            self.logger.debug(u'Recorded sound: %s' % sound)
            if not self.alsa.play_sound(sound, timeout=6.0):
                raise CommandError(u'Unable to play recorded sound: internal error')

            # release resource
            self._release_resource(u'audio.capture')

            # purge file
            time.sleep(0.5)
            try:
                os.remove(sound)
            except Exception:
                self.logger.warning(u'Unable to delete recorded test sound "%s"' % sound)

        else:
            self.logger.error(u'Unsupported resource "%s" acquired' % resource_name)

    def _resource_needs_to_be_released(self, resource_name): # pragma: no cover
        """
        Function called when resource is acquired by other module and needs to be released.

        Args:
            resource_name (string): acquired resource name
        """
        # resource is not acquired for too long, it will be released naturally so nothing to do here

