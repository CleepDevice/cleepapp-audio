/**
 * Audio config directive
 * Handle audio configuration
 */
var audioConfigDirective = function(toast, audioService, raspiotService) {

    var audioController = function()
    {
        var self = this;
        self.playbackDevices = [];
        self.captureDevices = [];
        self.config = {}
        self.volumePlayback = 0;
        self.volumeCapture = 0;
        self.currentDevice = null;

        /**
         * Set volumes
         */
        self.setVolumes = function()
        {
            audioService.setVolumes(self.volumePlayback, self.volumeCapture)
                .then(function(resp) {
                    self.volumePlayback = resp.data.playback;
                    self.volumeCapture = resp.data.capture;

                    toast.success('Volume saved successfully');
                });
        };

        /**
         * Set device
         */
        self.setDevice = function()
        {
            audioService.setDefaultDevice(self.currentDevice.cardid, self.currentDevice.deviceid)
                .then(function(resp) {
                    //reload module config to get new volumes
                    return raspiotService.reloadModuleConfig('audio');
                })
                .then(function(config) {
                    self.setConfig(config);
                    toast.success('Selected device is now the default audio card');
                });
        };

        /**
         * Play test sound
         */
        self.testPlaying = function()
        {
            audioService.testPlaying()
                .then(function() {
                    toast.success('You should have heard a sound');
                });
        };

        /**
         * Record voice and play it
         */
        self.testRecording = function()
        {
            toast.loading('Recording 5 seconds...');
            audioService.testRecording()
                .then(function() {
                    toast.success('You should have heard your recording');
                });
        };

        /**
         * Flatten specified object
         */
        self.flattenDict = function(obj)
        {
            out = []
            for( var item in obj )
            {
                out.push(obj[item]);
            }
            return out;
        };

        //set internal members according to config
        self.setConfig = function(config)
        {
            self.playbackDevices = self.flattenDict(config.devices.playback);
            self.captureDevices = self.flattenDict(config.devices.capture);
            self.config = config.config;
            self.volumePlayback = config.volumes.playback;
            self.volumeCapture = config.volumes.capture;

            if( !self.config )
            {
                //no config, nothing else to do
                return;
            }

            //search for current device in playback devices list
            for( var i=0; i<self.playbackDevices.length; i++ )
            {
                if( self.playbackDevices[i].cardid===self.config.cardid && self.playbackDevices[i].deviceid===self.config.deviceid )
                {
                    self.currentDevice = self.playbackDevices[i];
                }
            }
        };

        /**
         * Init controller
         */
        self.init = function()
        {
            raspiotService.getModuleConfig('audio')
                .then(function(config) {
                    self.setConfig(config);
                });
        };

    };

    var audioLink = function(scope, element, attrs, controller) {
        controller.init();
    };

    return {
        templateUrl: 'audio.directive.html',
        replace: true,
        scope: true,
        controller: audioController,
        controllerAs: 'audioCtl',
        link: audioLink
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('audioConfigDirective', ['toastService', 'audioService', 'raspiotService', audioConfigDirective])

