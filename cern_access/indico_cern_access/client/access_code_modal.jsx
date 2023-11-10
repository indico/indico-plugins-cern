// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2023 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import _ from 'lodash';
import PropTypes from 'prop-types';
import React, {useEffect, useState} from 'react';
import ReactDOM from 'react-dom';
import {Button, Divider, Header, Modal, Table} from 'semantic-ui-react';

import {Translate} from './i18n';

function AccessCodeModal({name, code, accompanyingCodes, triggerSelector}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!triggerSelector) {
      return;
    }
    const handler = () => setOpen(true);
    const elements = document.querySelector(triggerSelector);
    elements.addEventListener('click', handler);
    return () => elements.removeEventListener('click', handler);
  }, [triggerSelector]);

  return (
    <Modal open={open} onClose={() => setOpen(false)} size="tiny" closeIcon>
      <Header content={Translate.string('Access Code for {name}', {name})} />
      <Modal.Content>
        <p style={{textAlign: 'center'}}>
          <code style={{fontWeight: 'bold', fontSize: '2em'}}>{code}</code>
        </p>
        {accompanyingCodes.length > 0 && (
          <>
            <Divider />
            <p>
              <Translate>Access codes for the registrant's accompanying persons:</Translate>
            </p>
            <Table basic celled>
              <Table.Body>
                {_.sortBy(accompanyingCodes, 'name').map(({name: accName, code: accCode}) => (
                  <Table.Row key={accCode}>
                    <Table.Cell>{accName}</Table.Cell>
                    <Table.Cell>
                      <code style={{fontWeight: 'bold'}}>{accCode}</code>
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table>
          </>
        )}
      </Modal.Content>
      <Modal.Actions>
        <Translate as={Button} onClick={() => setOpen(false)}>
          Close
        </Translate>
      </Modal.Actions>
    </Modal>
  );
}

AccessCodeModal.propTypes = {
  name: PropTypes.string.isRequired,
  code: PropTypes.string.isRequired,
  accompanyingCodes: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      code: PropTypes.string.isRequired,
    })
  ).isRequired,
  triggerSelector: PropTypes.string.isRequired,
};

window.setupAccessCodeButton = function setupAccessCodeButton(container, trigger) {
  const element = document.querySelector(container);
  const {name, code, accompanyingCodes} = element.dataset;
  ReactDOM.render(
    <AccessCodeModal
      triggerSelector={trigger}
      name={name}
      code={code}
      accompanyingCodes={JSON.parse(accompanyingCodes)}
    />,
    element
  );
};
