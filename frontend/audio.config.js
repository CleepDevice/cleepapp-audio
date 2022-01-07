/**
 * Audio config component
 * Handle audio configuration
 */
angular
.module('Cleep')
.directive('audioConfigComponent', ['$rootScope', 'toastService', 'audioService', 'cleepService',
function($rootScope, toast, audioService, cleepService) {

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
        self.setVolumes = function() {
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
        self.setDevice = function() {
            if( !self.currentDevice ) {
                toast.info('Please select a device');
                return;
            }

            audioService.selectDevice(self.currentDevice.label)
                .then(function() {
                    toast.success('Audio device changed. Cleep will restart in few seconds');
                })
                .finally(function() {
                    //reload module config to get new volumes
                    return cleepService.reloadModuleConfig('audio');
                });
        };

        /**
         * Play test sound
         */
        self.testPlaying = function() {
            audioService.testPlaying()
                .then(function() {
                    toast.success('You should have heard a sound');
                });
        };

        /**
         * Record voice and play it
         */
        self.testRecording = function() {
            toast.loading('Recording 5 seconds...');
            audioService.testRecording()
                .then(function() {
                    toast.success('You will hear your record');
                });
        };

        //set internal members according to received config
        self.setConfig = function(config) {
            self.playbackDevices = config.devices.playback;
            self.captureDevices = config.devices.capture;
            self.volumePlayback = config.volumes.playback;
            self.volumeCapture = config.volumes.capture;

            //search for current device in playback devices list
            for( var i=0; i<self.playbackDevices.length; i++ ) {
                if( self.playbackDevices[i].enabled===true ) {
                    self.currentDevice = self.playbackDevices[i];
                    break;
                }
            }
        };

        /**
         * Init component
         */
        self.$onInit = function() {
            cleepService.getModuleConfig('audio')
                .then(function(config) {
                    self.setConfig(config);
                });
        };

     	/**
      	 * Watch for config changes
      	 */
     	$rootScope.$watchCollection(function() {
        	return cleepService.modules['audio'];
     	}, function(newConfig, oldConfig) {
        	if( newConfig )
         	{
            	self.setConfig(newConfig.config);
         	}
     	});
    };

    return {
        templateUrl: 'audio.config.html',
        replace: true,
        scope: true,
        controller: audioController,
        controllerAs: 'audioCtl',
    };
}]);
