#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import os
from raspiot.raspiot import RaspIotResource
from raspiot.libs.commands.alsa import Alsa
from raspiot.libs.configs.asoundrc import Asoundrc

__all__ = ['Audio']


class Audio(RaspIotResource):
    """
    Audio module is in charge of configuring audio on raspberry pi
    """
    MODULE_AUTHOR = u'Cleep'
    MODULE_VERSION = u'1.0.0'
    MODULE_PRICE = 0
    MODULE_DEPS = []
    MODULE_DESCRIPTION = u'Configure audio on your device'
    MODULE_LOCKED = True
    MODULE_TAGS = [u'audio', u'sound']
    MODULE_COUNTRY = None
    MODULE_URLINFO = None
    MODULE_URLHELP = None
    MODULE_URLBUGS = None
    MODULE_URLSITE = None

    MODULE_CONFIG_FILE = None

    TEST_SOUND = u'/opt/raspiot/sounds/connected.wav'

    DEFAULT_DEVICE = {
        u'card': 0,
        u'device': 0
    }
    RESOURCES = {
        u'audio.capture': 50.0,
        u'audio.playback': 75.0
    }

    def __init__(self, bootstrap, debug_enabled):
        """
        Constructor

        Args:
            bootstrap (dict): bootstrap objects
            debug_enabled (bool): flag to set debug level to logger
        """
        #init
        RaspIotResource.__init__(self, self.RESOURCES, bootstrap, debug_enabled)

        #members
        self.alsa = Alsa(self.cleep_filesystem)
        self.asoundrc = Asoundrc(self.cleep_filesystem)

    def _configure(self):
        """
        Module configuration
        """
        if not self.asoundrc.exists():
            self.logger.debug(u'Create default audio configuration file')
            self.asoundrc.set_default_device(self.DEFAULT_DEVICE[u'card'], self.DEFAULT_DEVICE[u'device'])

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
        volumes = self.alsa.get_volumes()

        #improve configuration content
        card_name = None
        if current_config is not None:
            for name in playback_devices.keys():
                if playback_devices[name][u'cardid']==current_config[u'cardid']:
                    card_name = name
                    break
            current_config[u'cardname'] = card_name

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
        #get playback resource
        self.acquire_resource(u'audio.playback')

        #play audio
        if not self.alsa.play_sound(self.TEST_SOUND):
            raise CommandError(u'Unable to play test sound: internal error.')

        #release resource
        self.release_resource(u'audio.playback')

    def test_recording(self):
        """
        Record sound during few seconds and play it
        """
        #get capture resource
        self.acquire_resource(u'audio.capture')

        #record sound
        sound = self.alsa.record_sound(timeout=5.0)
        self.logger.debug(u'Recorded sound: %s' % sound)
        self.alsa.play_sound(sound)

        #release resource
        self.release_resource(u'audio.capture')

        #purge file
        time.sleep(0.5)
        os.remove(sound)

    def _acquire_resource(self, resource, extra):
        """
        Acquire resource

        Args:
            resource (string): resource name
            extra (dict): extra parameters

        Return:
            bool: True if resource acquired
        """
        #nothing to perform here
        return True

    def _release_resource(self, resource, extra):
        """
        Release resource

        Args:
            resource (string): resource name
            extra (dict): extra parameters

        Return:
            bool: True if resource acquired
        """
        #resource is not acquired during too much time, so do nothing
        return True


