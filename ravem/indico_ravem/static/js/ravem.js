(function() {
    'use strict';
    var ravemButton = (function makeRavemButton() {
        var POOLING_DELAY = 5000;  // milliseconds
        var states = {
            connected: {
                icon: 'icon-no-camera',
                tooltip: $T('Disconnect {0} from the Vidyo room {1}'),
                action: 'disconnect',
                handler: function disconnectHandler(data, btn) {
                    var name = btn.data('roomName');
                    var vcRoomName = btn.data('vcRoomName');

                    var states = {
                        old: 'connected',
                        new: 'disconnected',
                        error: 'errorDisconnect',
                        wait: 'waitingDisconnect'
                    };
                    var messages = {
                        alreadyConnected: $T('Would you like to force the room {0} to disconnect?').format(name),
                        error:  $T('Failed to disconnect the room {0} from the Vidyo room').format(name, vcRoomName),
                    };

                    _handler(data, btn, states, ['already-disconnected'], messages, function checkDisconnected(status, btn) {
                        return !status.connected || status.vc_room_name !== vcRoomName;
                    });
                }
            },
            disconnected: {
                icon: 'icon-camera',
                tooltip: $T('Connect {0} to the Vidyo room {1}'),
                action: 'connect',
                handler: function connectHandler(data, btn) {
                    var name = btn.data('roomName');
                    var vcRoomName = btn.data('vcRoomName');
                    var states = {
                        old: 'disconnected',
                        new: 'connected',
                        error: 'errorConnect',
                        wait: 'waitingConnect'
                    };
                    var messages = {
                        alreadyConnected: $T('Would you like to force the room {0} to connect to your Vidyo room ({1}) ?').format(name, vcRoomName),
                        error:  $T('Failed to connect the room {0} to the Vidyo room').format(name, vcRoomName)
                    };

                    _handler(data, btn, states, ['already-connected'], messages, function checkConnect(status, btn){
                        return status.connected && status.vc_room_name === vcRoomName;
                    });
                }
            },
            errorConnect: {
                tooltip: $T("Failed to connect {0} to the Vidyo room {1}. Please wait a moment and refresh the page to try again."),
                tooltipType: 'error',
                icon: 'icon-warning',
            },
            errorDisconnect: {
                tooltip: $T("Failed to disconnect {0} from the Vidyo room {1}. Please wait a moment and refresh the page to try again."),
                tooltipType: 'error',
                icon: 'icon-warning',
            },
            errorStatus: {
                tooltip: $T("Failed to contact {0}. Please wait a moment and refresh the page to try again."),
                tooltipType: 'error',
                icon: 'icon-warning',
            },
            waitingConnect: {
                icon: 'icon-spinner',
                tooltip: $T("Connecting {0} to the Vidyo room {1}"),
            },
            waitingDisconnect: {
                icon: 'icon-spinner',
                tooltip: $T("Disconnecting {0} from the Vidyo room {1}"),
            },
            waitingStatus: {
                icon: 'icon-spinner',
                tooltip: $T("Waiting for information about {0}"),
            }
        };

        function _handler(data, btn, states, validReasons, messages, checkFn) {
            var name = btn.data('roomName');

            if (data.success) {
                var attempts = 4;
                var timer = window.setTimeout(function assertActionSuccessful() {
                    if (!attempts) {
                        clearTimeout(timer);
                        setButtonState(btn, states.error);
                        return;
                    }
                    getRoomStatus(btn)
                        .fail(function statusUpdateErrorHandler() {
                            attempts--;
                            timer = window.setTimeout(assertActionSuccessful, POOLING_DELAY);
                        })
                        .done(function statusUpdateHandler(status) {
                            if (!checkFn(status, btn)) {
                                attempts--;
                                timer = window.setTimeout(assertActionSuccessful, POOLING_DELAY);
                            } else {
                                clearTimeout(timer);
                                setButtonState(btn, states.new);
                            }
                    });
                }, POOLING_DELAY);

            } else if (data.reason in validReasons) {
                setButtonState(btn, states.new);

            } else if (data.reason === 'connected-other') {
                new ConfirmPopup(
                    $T('{0} already connected').format(name), [
                        data.message.replace('\n', '<br>'),
                        messages.alreadyConnected
                    ].join('<br>'),
                    function forceDisconnectPopup(forceDisconnect) {
                        setButtonState(btn, states.old);
                        if (forceDisconnect) {
                            sendRequest(btn, states.wait, true).done(function(newData) {
                                _handler(newData, btn, states, validReasons, checkFn, messages);
                            });
                        }
                }).open();

            } else {
                new ErrorPopup(
                    messages.error,
                    data.message.split('\n'),
                    $T('Please refresh the page and try again')
                ).open();
                setButtonState(btn, states.error);
            }
        }

        function setButtonState(btn, newState) {
            btn.data('state', newState);

            var name = btn.data('roomName');
            var vcRoomName = btn.data('vcRoomName');
            var html = ['<span class="', states[newState].icon,
                        '"><strong style="margin-left: 0.4em;">{0}</strong></span>'.format(name)].join('');

            btn.html(html);
            btn.toggleClass('disabled', !states[newState].action);

            var qtip = {
                content: states[newState].tooltip.format(name, vcRoomName),
                position: {my: 'top center', at: 'bottom center'},
                show: 'mouseover', hide: 'mouseout'
            };
            if ('tooltipType' in states[newState]) {
                qtip.style = {classes: 'qtip-' + states[newState].tooltipType};
            }
            btn.qtip('destroy', true);
            btn.qtip(qtip);
        }

        function clickHandler(e) {
            e.preventDefault();
            var btn = $(this);

            if (btn.hasClass('disabled')) {
                return;
            }

            var state = btn.data('state');
            switch(state) {
                case 'connected':
                    sendRequest(btn, 'waitingDisconnect')
                        .done(function onConnect(data) {
                            states.connected.handler(data, btn);
                        });
                    break;
                case 'disconnected':
                    sendRequest(btn, 'waitingConnect')
                        .done(function onDisconnect(data) {
                            states.disconnected.handler(data, btn);
                        });
                    break;
                default:
                    new ErrorPopup(
                        $T("Something went wrong."),
                        [$T("Unknown error")],
                        $T("Please refresh the page and try again.")
                    ).open();
            }
        }

        function _sendRequest(btn, type, url, waitingState) {
            if (waitingState) {
                setButtonState(btn, waitingState);
            }

            var deferred = $.Deferred();
            $.ajax({
                type: type,
                url: url,
                error: function errorHandler(xhr) {
                    handleAjaxError(xhr);
                    deferred.reject(xhr);
                },
                success: function successHandler(data) {
                    deferred.resolve(data);
                }
            });
            return deferred.promise();
        }

        function sendRequest(btn, waitingState, force) {
            force = force || false;
            var state = btn.data('state');
            var url = btn.data(states[state].action + 'Url');
            if (force) {
                url = build_url(url, {force: '1'});
            }

            return _sendRequest(btn, 'POST', url, waitingState);
        }

        function getRoomStatus(btn, waitingState) {
            return _sendRequest(btn, 'GET', btn.data('statusUrl'), waitingState);
        }

        function initializeRavemButton(btn) {
            btn.on('click', clickHandler);
            var vcRoomName = btn.data('vcRoomName');
            getRoomStatus(btn, 'waitingStatus')
                .fail(function errorHandler() {
                    setButtonState(btn, 'errorStatus');
                })
                .done(function successHandler(data) {
                    if (!data.success) {
                        setButtonState(btn, 'errorStatus');
                    } else {
                        var connected = data.connected && data.vc_room_name === vcRoomName;
                        setButtonState(btn, connected ? 'connected' : 'disconnected');
                    }
                });
            return btn;
        }

        return initializeRavemButton;
    })();

    $(document).ready(function() {
        $('.js-ravem-button').each(function() {
            ravemButton($(this));
        });
    });
})();
