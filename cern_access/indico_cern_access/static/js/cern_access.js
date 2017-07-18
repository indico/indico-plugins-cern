(function() {
    'use strict';
    $(document).ready(function() {
        var $valueField = $('input#request-regforms');
        var hiddenData = JSON.parse($valueField.val());

        $('#regforms-list .switch-input').on('change', function() {
            var $this = $(this);
            var regformId = +$this.val();
            var allowUnpaid = $('#allow_unpaid_' + regformId);
            if ($this.is(':checked')) {
                var regformInfo = {
                    allow_unpaid: false,
                    regform_id: regformId
                };
                allowUnpaid.prop('disabled', false);
                hiddenData.regforms.push(regformInfo);
            } else {
                for (var i = 0; i < hiddenData.regforms.length; i++) {
                    if (hiddenData.regforms[i].regform_id === regformId) {
                        hiddenData.regforms.splice(i, 1);
                        allowUnpaid.prop('disabled', true);
                        allowUnpaid.prop('checked', false);
                    }
                }
            }
            hiddenData.regforms.sort(sortById);
            $valueField.val(JSON.stringify(hiddenData));
        });

        $("input[name='allow_unpaid']").on('change', function(){
            var $this = $(this);
            var regformId = parseInt($(this).val());
            if ($this.prop('checked')){
                hiddenData.regforms.forEach(function(regform){
                    if (regform.regform_id === regformId){
                        regform.allow_unpaid = true;
                    }
                })
            } else {
                hiddenData.regforms.forEach(function(regform){
                    if (regform.regform_id === regformId){
                        regform.allow_unpaid = false;
                    }
                })
            }
            $valueField.val(JSON.stringify(hiddenData));
        });
     });

    function sortById(a, b){
        var aId = a.regform_id;
        var bId = b.regform_id;
        return ((aId < bId) ? -1 : ((aId > bId) ? 1 : 0));
    }
})();



