/**
 * Audio service
 * Handle audio module requests
 */
var audioService = function($q, $rootScope, rpcService) {
    var self = this;

    self.setVolumes = function(playback, capture) {
        return rpcService.sendCommand('set_volumes', 'audio', {'playback':playback, 'capture':capture});
    };

    self.setDefaultDevice = function(cardName) {
        return rpcService.sendCommand('set_default_device', 'audio', {'device_name':cardName});
    };

    self.testPlaying = function()
    {
        return rpcService.sendCommand('test_playing', 'audio');
    };

    self.testRecording = function()
    {
        return rpcService.sendCommand('test_recording', 'audio', null, 30);
    };

};
    
var RaspIot = angular.module('RaspIot');
RaspIot.service('audioService', ['$q', '$rootScope', 'rpcService', audioService]);

