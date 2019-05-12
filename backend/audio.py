#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import os
import copy
from raspiot.raspiot import RaspIotResources
from raspiot.utils import CommandError, CommandInfo, InvalidParameter, MissingParameter
from raspiot.libs.commands.alsa import Alsa
from raspiot.libs.configs.etcasoundconf import EtcAsoundConf
from raspiot.libs.drivers.driver import Driver
from .bcm2835audiodriver import Bcm2835AudioDriver

__all__ = ['Audio']


class Audio(RaspIotResources):
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
    MODULE_CORE = True
    MODULE_TAGS = [u'audio', u'sound']
    MODULE_COUNTRY = None
    MODULE_URLINFO = u'https://github.com/tangb/cleepmod-audio'
    MODULE_URLHELP = u'https://github.com/tangb/cleepmod-audio/wiki'
    MODULE_URLBUGS = u'https://github.com/tangb/cleepmod-audio/issues'
    MODULE_URLSITE = None

    MODULE_CONFIG_FILE = None

    TEST_SOUND = u'/opt/raspiot/sounds/connected.wav'

    DEFAULT_DEVICE = {
        u'card': 0,
        u'device': 0
    }

    MODULE_RESOURCES = {
        u'Raspberrypi soundcard': {
            u'audio.playback': {
                u'hardware_id': u'bcm2835 ALSA',
                u'permanent': False,
            }
        }
    }

    def __init__(self, bootstrap, debug_enabled):
        """
        Constructor

        Args:
            bootstrap (dict): bootstrap objects
            debug_enabled (bool): flag to set debug level to logger
        """
        #init
        RaspIotResources.__init__(self, bootstrap, debug_enabled)

        #members
        self.alsa = Alsa()
        self.asoundconf = EtcAsoundConf(self.cleep_filesystem)
        self.bcm2835_driver = Bcm2835AudioDriver(self.cleep_filesystem, 'Raspberry pi soundcard')
        self.__cached_playback_devices = None
        self.__cached_capture_devices = None

    def _configure(self):
        """
        Module configuration
        """
        if not self.asoundconf.exists():
            self.logger.debug(u'No audio config found set default one')
            self._set_default_config()

        #register default audio drivers
        self._register_driver(self.bcm2835_driver)

    def _set_default_config(self):
        """
        Set default config. Use it when fatal error occured
        It restores config for default raspberry audio device bcm2835.
        """
        self.bcm2835_driver.enable()

    def _get_driver(self, card_name, audio_drivers=None):
        """
        Return driver according to specified parameters

        Args:
            card_name (string): card name
            audio_drivers (list): list of audio drivers. If None get it from drivers

        Returns:
            AudioDriver: driver instance or None if not found
        """
        if audio_drivers is None:
            audio_drivers = self.drivers.get_drivers(Driver.DRIVER_AUDIO)

        for _, driver in audio_drivers.items():
            device_infos = driver.get_device_infos()
            if device_infos[u'cardname']==card_name:
                self.logger.debug(u'Found driver "%s" for current audio device "%s"' % (driver.name, card_name))
                return driver

        return None

    def _get_current_driver(self, selected_device=None, audio_drivers=None):
        """
        Return current driver for selected audio device

        Args:
            selected_device (dict): selected device infos. If None get it from alsa lib
            audio_drivers (list): list of audio drivers. If None get it from drivers

        Returns:
            AudioDriver: current audio driver or None if device not found
        """
        if selected_device is None:
            selected_device = self.alsa.get_selected_device()

        return self._get_driver(selected_device[u'name'], audio_drivers) if selected_device else None

    def _get_current_volumes(self, selected_device, audio_drivers):
        """
        Get currently configured volumes

        Args:
            selected_device (dict): current selected audio device. Provided for performance
            audio_drivers (list): list of audio drivers. Provided for performance

        Returns:
            dict: volumes or None if not found::

                {
                    playback (int): playback volume
                    capture (int): capture volume
                }

        """
        driver = self._get_current_driver(selected_device)
        return driver.get_volumes() if driver else None

    def _fill_devices_cache(self, audio_drivers):
        """
        Fill devices list the first time config is loaded

        Args:
            audio_drivers (list): list of audio drivers
        """
        self.__cached_playback_devices = self.alsa.get_playback_devices()
        self.__cached_capture_devices = self.alsa.get_capture_devices()

        #get supported device names
        handled_device_names = {}
        for _, driver in audio_drivers.items():
            device_infos = driver.get_device_infos()
            handled_device_names[device_infos[u'cardname']] = driver.name

        #fill cache
        for _, device in self.__cached_playback_devices.items():
            if device[u'name'] in handled_device_names:
                device[u'label'] = handled_device_names[device[u'name']]
                device[u'supported'] = True
            elif u'label' not in device:
                device[u'label'] = device[u'name']
                device[u'supported'] = False
        for _, device in self.__cached_capture_devices.items():
            if device[u'name'] in handled_device_names:
                device[u'label'] = handled_device_names[device[u'name']]
                device[u'supported'] = True
            elif u'label' not in device:
                device[u'label'] = device[u'name']
                device[u'supported'] = False

    def get_module_config(self):
        """
        Return module configuration

        Returns:
            dict: audio config::

                {
                    config (dict): config from asoundrc file
                    volumes (dict): volumes values (playback and capture)
                    devices (dict): audio devices installed on device (playback and capture)
                }

        """
        #gather audio informations
        audio_drivers = self.drivers.get_drivers(Driver.DRIVER_AUDIO)
        selected_device = self.alsa.get_selected_device()

        #get playback and capture devices
        if not self.__cached_playback_devices or not self.__cached_capture_devices:
            self._fill_devices_cache(audio_drivers)
        playback_devices = copy.deepcopy(self.__cached_playback_devices)
        capture_devices = copy.deepcopy(self.__cached_capture_devices)

        #get volume for current selected device
        volumes = self._get_current_volumes(selected_device, audio_drivers)
        if volumes is None:
            self.logger.warn(u'Invalid audio configuration detected. Force default configuration.')
            self._set_default_config()

            #get again volumes
            volumes = self._get_current_volumes(selected_device, audio_drivers)

        #set selected flag (only for playback)
        for device_name, device in playback_devices.items():
            if device[u'name']==selected_device[u'name']:
                device[u'selected'] = True
            else:
                device[u'selected'] = False

        return {
            u'volumes': {
                u'playback': volumes[u'playback'] if volumes else None,
                u'capture': volumes[u'capture'] if volumes else None,
            },
            u'devices': {
                u'playback': sorted(playback_devices.values(), key=lambda k:k[u'label']),
                u'capture': sorted(capture_devices.values(), key=lambda k:k[u'label']),
            }
        }

    def set_default_device(self, device_name):
        """
        Set default audio device

        Args:
            device_name (int): device name

        Returns:
            bool: True if device saved successfully

        Raises:
            InvalidParameter: if parameter is invalid
        """
        #get drivers
        old_driver = self._get_current_driver()
        new_driver = self._get_driver(device_name)
        
        if not new_driver:
            raise InvalidParameter(u'No driver installed from specified device')
        self.logger.info(u'Set default audio device to: %s' % new_driver.name)

        #check if already selected
        if old_driver.name==new_driver.name:
            self.logger.info(u'Audio device is already selected. Nothing changed')
            return True

        #enable driver
        self.logger.debug(u'Disable previous driver: %s' % old_driver.name)
        old_driver.disable()
        return new_driver.enable()
    
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

        """
        self.logger.info(u'Set volumes to: playback[%s%%] capture[%s%%]' % (playback, capture))
        volumes = None

        driver = self._get_current_driver()
        if driver:
            volumes = driver.set_volumes(playback, capture)
        
        return {
            u'playback': volumes[u'playback'] if volumes else None,
            u'capture': volumes[u'capture'] if volumes else None,
        }

    def test_playing(self):
        """
        Play test sound to make sure audio card is correctly configured
        """
        #request playback resource
        self._need_resource(u'audio.playback')

    def test_recording(self):
        """
        Record sound during few seconds and play it
        """
        #request capture resource
        self._need_resource(u'audio.capture')

    def _resource_acquired(self, resource_name):
        """
        Function called when resource is acquired

        Args:
            resource_name (string): acquired resource name

        Raises:
            CommandError: if command failed
        """
        self.logger.debug('Resource "%s" acquired' % resource_name)
        if resource_name==u'audio.playback':
            #play test sample
            if not self.alsa.play_sound(self.TEST_SOUND):
                raise CommandError(u'Unable to play test sound: internal error.')

            #release resource
            self._release_resource(u'audio.playback')

        elif resource_name==u'audio.capture':
            #record sound
            sound = self.alsa.record_sound(timeout=5.0)
            self.logger.debug(u'Recorded sound: %s' % sound)
            self.alsa.play_sound(sound)

            #release resource
            self._release_resource(u'audio.capture')

            #purge file
            time.sleep(0.5)
            try:
                os.remove(sound)
            except:
                self.logger.warn(u'Unable to remove recorded test sound "%s"' % sound)

        else:
            self.logger.error(u'Unsupported resource "%s" acquired' % resource_name)

    def _resource_needs_to_be_released(self, resource_name):
        """
        Function called when resource is acquired by other module and needs to be released.

        Args:
            resource_name (string): acquired resource name
        """
        #resource is not acquired for too long, it will be released naturally so nothing to do here
        pass

