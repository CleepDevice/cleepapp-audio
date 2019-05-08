#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import os
from raspiot.raspiot import RaspIotResources
from raspiot.utils import CommandError, CommandInfo, InvalidParameter, MissingParameter
from raspiot.libs.commands.alsa import Alsa
from raspiot.libs.configs.asoundrc import Asoundrc
from raspiot.libs.drivers.audiodriver import AudioDriver
from raspiot.libs.drivers.driver import Driver

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
        u'Raspberrypi soundcard (jack)': {
            u'audio.playback': {
                u'hardware_id': u'bcm2835 ALSA',
                u'permanent': False,
            }
        },
        u'Raspberrypi soundcard (HDMI)': {
            u'audio.playback': {
                u'hardware_id': u'bcm2835 IEC958/HDMI',
                u'permanent': False,
            }
        }
    }

    AUDIO_DRIVERS = {
        u'bcm2835 ALSA': {
            u'output_type': AudioDriver.OUTPUT_TYPE_JACK,
            u'playback_volume': u'PCM',
            u'playback_volume_data': (u'Mono', r'\[(\d*)%\]'),
            u'capture_volume': None,
            u'capture_volume_data': None,
        },
        u'bcm2835 IEC958/HDMI': {
            u'output_type': AudioDriver.OUTPUT_TYPE_HDMI,
            u'playback_volume': u'PCM',
            u'playback_volume_data': (u'Mono', r'\[(\d*)%\]'),
            u'capture_volume': None,
            u'capture_volume_data': None,
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
        self.alsa = Alsa(self.drivers, self.cleep_filesystem)
        self.asoundrc = Asoundrc(self.cleep_filesystem)

    def _configure(self):
        """
        Module configuration
        """
        if not self.asoundrc.exists():
            self.logger.debug(u'No audio config found set default one')
            self._set_default_config()

        #register default audio drivers (for jack and HDMI outputs)
        for driver_name, driver in self.AUDIO_DRIVERS.items():
            self._register_driver(AudioDriver(driver_name, driver))

    def _set_default_config(self):
        """
        Set default config. Use it when fatal error occured
        It restores config for default raspberry audio device bcm2835.
        """
        self.asoundrc.set_default_device(self.DEFAULT_DEVICE[u'card'], self.DEFAULT_DEVICE[u'device'])
        #make sure file is written
        time.sleep(0.5)

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
        #get all stuff
        current_config = self.asoundrc.get_configuration()
        self.logger.debug('current_config=%s' % current_config)
        playback_devices = self.alsa.get_playback_devices()
        capture_devices = self.alsa.get_capture_devices()
        try:
            volumes = self.alsa.get_volumes()
        except:
            #unable to get volumes, surely invalid device is configured, restore default config
            self.logger.warn(u'Invalid audio configuration detected. Force default configuration.')
            self._set_default_config()
            #get again volumes
            volumes = self.alsa.get_volumes()

        #improve audio devices adding label
        audio_resources = self._get_resources('audio\.')
        if u'audio.playback' in audio_resources:
            for device_name, device in playback_devices.items():
                if device[u'cardid']==current_config[u'cardid'] and device[u'deviceid']==current_config[u'deviceid']:
                    device.update({u'selected': True})
                else:
                    device.update({u'selected': False})
                if device_name in audio_resources[u'audio.playback']:
                    device.update({u'label': audio_resources[u'audio.playback'][device_name][u'label']})
                else:
                    device.update({u'label': device[u'name']})
        if u'audio.capture' in audio_resources:
            for device_name, device in capture_devices.items():
                if device[u'cardid']==current_config[u'cardid'] and device[u'deviceid']==current_config[u'deviceid']:
                    device.update({u'selected': True})
                else:
                    device.update({u'selected': False})
                if device_name in audio_resources[u'audio.capture']:
                    device.update({u'label': audio_resources[u'audio.capture'][device_name][u'label']})
                else:
                    device.update({u'label': device[u'name']})

        return {
            u'config': current_config,
            u'volumes': volumes,
            u'devices': {
                u'playback': playback_devices,
                u'capture': capture_devices
            }
        }

    def set_default_device(self, card_id, device_id):
        """
        Set default audio device

        Args:
            card_id (int): card identifier
            device_id (int): device identifier

        Return:
            bool: True if device saved successfully
        """
        #check values
        playback_devices = self.alsa.get_playback_devices()
        found = False
        for device in playback_devices.keys():
            if playback_devices[device][u'cardid']==card_id and playback_devices[device][u'deviceid']==device_id:
                found = True
                break
        if not found:
            raise InvalidParameter(u'Specified device is not installed')

        #save new device
        return self.asoundrc.set_default_device(card_id, device_id)
    
    def set_volumes(self, playback, capture):
        """
        Update volume

        Args:
            playback (int): playback volume percentage
            capture (int): capture volume percentage

        Return:
            dict: current volume::
                {
                    playback (int)
                    capture (int)
                }
        """
        return self.alsa.set_volumes(playback, capture)

    def test_playing(self):
        """
        Play test sound to make sure audio card is correctly configured
        """
        #request playback resource
        self._need_resource(u'audio.playback')
        raise CommandInfo('Audio sample will be played in few seconds')

    def test_recording(self):
        """
        Record sound during few seconds and play it
        """
        #request capture resource
        self._need_resource(u'audio.capture')
        raise CommandInfo('Recording will start in few seconds. Please wait for message.')

    def _resource_acquired(self, resource_name):
        """
        Function called when resource is acquired

        Args:
            resource_name (string): acquired resource name
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

