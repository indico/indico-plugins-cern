// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2022 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import './style.scss';

(function() {
  function checkConversion(ids) {
    $.ajax({
      url: ConversionPlugin.urls.check,
      method: 'GET',
      data: {a: ids},
      error: handleAjaxError,
      success(data) {
        if (handleAjaxError(data)) {
          return;
        }

        if (data.pending.length) {
          setTimeout(function() {
            checkConversion(data.pending);
          }, 10000);
        }

        _.each(data.finished, function(id) {
          const placeholder = $('.pdf-pending[data-attachment-id="{0}"]'.format(id));
          if (id in data.containers) {
            const newContainer = $(data.containers[id]);
            placeholder.closest('.attachments-display-container').replaceWith(newContainer);
            newContainer
              .find('.attachments > .i-dropdown')
              .parent()
              .dropdown();
          }
        });
      },
    });
  }

  $(document).ready(function() {
    const ids = $('.pdf-pending')
      .map(function() {
        return $(this).data('attachmentId');
      })
      .get();
    if (ids.length) {
      setTimeout(function() {
        checkConversion(ids);
      }, 5000);
    }
  });
})();
