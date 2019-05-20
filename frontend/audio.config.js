/**
 * Audio config directive
 * Handle audio configuration
 */
var audioConfigDirective = function($rootScope, toast, audioService, raspiotService) {

    var audioController = function()
    {
        var self = this;
        self.playbackDevices = [];
        self.captureDevices = [];
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
            if( !self.currentDevice ) {
                toast.info('Please select a device');
                return;
            }

            audioService.selectDevice(self.currentDevice.label)
                .then(function(resp) {
                    //reload module config to get new volumes
                    return raspiotService.reloadModuleConfig('audio');
                })
                .then(function() {
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

        //set internal members according to received config
        self.setConfig = function(config)
        {
            self.playbackDevices = config.devices.playback;
            self.captureDevices = config.devices.capture;
            self.volumePlayback = config.volumes.playback;
            self.volumeCapture = config.volumes.capture;

            //search for current device in playback devices list
            for( var i=0; i<self.playbackDevices.length; i++ )
            {
                if( self.playbackDevices[i].enabled===true )
                {
                    self.currentDevice = self.playbackDevices[i];
                    break;
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

     	/**
      	 * Watch for config changes
      	 */
     	$rootScope.$watchCollection(function() {
        	return raspiotService.modules['audio'];
     	}, function(newConfig, oldConfig) {
        	if( newConfig )
         	{
            	self.setConfig(newConfig.config);
         	}
     	});
    };

    var audioLink = function(scope, element, attrs, controller) {
        controller.init();
    };

    return {
        templateUrl: 'audio.config.html',
        replace: true,
        scope: true,
        controller: audioController,
        controllerAs: 'audioCtl',
        link: audioLink
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('audioConfigDirective', ['$rootScope', 'toastService', 'audioService', 'raspiotService', audioConfigDirective])

