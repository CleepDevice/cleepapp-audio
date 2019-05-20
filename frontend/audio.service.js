/**
 * Audio service
 * Handle audio module requests
 */
var audioService = function($q, $rootScope, rpcService) {
    var self = this;

    self.setVolumes = function(playback, capture) {
        return rpcService.sendCommand('set_volumes', 'audio', {'playback':playback, 'capture':capture});
    };

    self.selectDevice = function(label) {
        return rpcService.sendCommand('select_device', 'audio', {'driver_name':label}, 30.0);
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

