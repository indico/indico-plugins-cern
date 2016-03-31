from __future__ import unicode_literals

from operator import attrgetter

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from indico.core.db import db
from indico.modules.events.agreements.models.agreements import Agreement
from indico.modules.events.contributions.models.legacy_mapping import (LegacyContributionMapping,
                                                                       LegacySubContributionMapping)
from indico.util.console import cformat, verbose_iterator
from indico.util.string import sanitize_email

from indico_audiovisual.definition import SpeakerPersonInfo
from indico_audiovisual.util import contribution_id
from indico_zodbimport import Importer, convert_to_unicode


class AVRequestsImporter(Importer):
    plugins = {'audiovisual'}

    def migrate(self):
        self.migrate_agreement_data()

    def migrate_agreement_data(self):
        self.print_step("Migrating agreement data")
        query = Agreement.query.options(joinedload('event_new'))
        if self.quiet:
            it = verbose_iterator(query, query.count(), attrgetter('event_new.id'), attrgetter('event_new.title'))
        else:
            it = iter(query)
        for agreement in it:
            if agreement.event_new.is_deleted:
                continue
            link = self._get_person_link(agreement)
            if link is None:
                continue
            # del agreement.data['speaker_id']
            if not link.email:
                assert not agreement.person_email
            agreement.person_email = link.email
            agreement.data['id'] = link.id
            agreement.data['person_id'] = link.person_id
            if agreement.data['type'] == 'contribution':
                agreement_contrib_id = agreement.data.get('_legacy_contribution', agreement.data['contribution'])
                if '-' in agreement_contrib_id:
                    parts = agreement_contrib_id.split('-')
                    contrib = (LegacySubContributionMapping
                               .find(event_id=agreement.event_id, legacy_contribution_id=parts[0],
                                     legacy_subcontribution_id=parts[1])
                               .first()
                               .subcontribution)
                else:
                    contrib = (LegacyContributionMapping
                               .find(event_id=agreement.event_id, legacy_contribution_id=agreement_contrib_id)
                               .first()
                               .contribution)
                if '_legacy_contribution' not in agreement.data:
                    agreement.data['_legacy_contribution'] = agreement.data['contribution']
                agreement.data['contribution'] = contribution_id(contrib)
            spi = SpeakerPersonInfo(agreement.person_name, agreement.person_email or None, data=agreement.data)
            agreement.identifier = spi.identifier
            flag_modified(agreement, 'data')
            db.session.flush()
        db.session.commit()

    def _get_email(self, old_person):
        email = old_person._email
        return sanitize_email(convert_to_unicode(email).lower()) if email else email

    def _get_person_link(self, agreement):
        conf = self.zodb_root['conferences'][str(agreement.event_id)]
        speaker_id = int(agreement.data['speaker_id'])
        if agreement.data['type'] == 'lecture_speaker':
            old_person = next((x for x in conf._chairs if int(x._id) == speaker_id), None)
            if old_person is None:
                self.print_warning(cformat('%{yellow}Lecturer not found%{reset}: {}').format(agreement.data),
                                   event_id=agreement.event_id)
                return None
            links = agreement.event_new.person_links
        elif agreement.data['type'] == 'contribution':
            agreement_contrib_id = agreement.data.get('_legacy_contribution', agreement.data['contribution'])
            contrib_id, __, subcontrib_id = agreement_contrib_id.partition('-')
            contrib = conf.contributions.get(contrib_id)
            if contrib is None:
                self.print_warning(cformat('%{yellow}Contribution not found%{reset}: {}').format(agreement.data),
                                   event_id=agreement.event_id)
                return None
            if not subcontrib_id:
                old_person = next((x for x in contrib._speakers if int(x._id) == speaker_id), None)
                links = (agreement.event_new.legacy_contribution_mappings
                         .filter_by(legacy_contribution_id=contrib_id)
                         .one()
                         .contribution
                         .person_links)
                links = [x for x in links if x.is_speaker]
            else:
                contrib = next((x for x in contrib._subConts if x.id == subcontrib_id), None)
                if contrib is None:
                    self.print_warning(cformat('%{yellow}Subcontribution not found%{reset}: {}').format(agreement.data),
                                       event_id=agreement.event_id)
                    return None
                old_person = next((x for x in contrib.speakers if int(x._id) == speaker_id), None)
                links = (agreement.event_new.legacy_subcontribution_mappings
                         .filter_by(legacy_contribution_id=contrib_id, legacy_subcontribution_id=subcontrib_id)
                         .one()
                         .subcontribution
                         .person_links)
            if old_person is None:
                self.print_warning(cformat('%{yellow}Speaker not found%{reset}: {}').format(agreement.data),
                                   event_id=agreement.event_id)
                return None
        else:
            raise ValueError(agreement.data['type'])

        if not links:
            self.print_error('No person links found', event_id=agreement.event_id)
            return None

        # try to find the link based on the email
        email = self._get_email(old_person)
        if email:
            for link in links:
                if link.email == email or (link.person.user and email in link.person.user.all_emails):
                    return link
        if email:
            self.print_warning('Could not match speaker by email: {} ({})'
                               .format(email, ', '.join(link.email or '-' for link in links)),
                               event_id=agreement.event_id)
            return None
        # try to find it based on the name
        candidates = []
        for link in links:
            if (link.first_name == convert_to_unicode(old_person._firstName) and
                    link.last_name == convert_to_unicode(old_person._surName)):
                candidates.append(link)
        if len(candidates) == 1:
            return candidates[0]
        elif len(candidates) > 1:
            self.print_error('Multiple candidates for {} {}: {}'
                             .format(old_person._firstName, old_person._surName,
                                     ', '.join(c.full_name for c in candidates)),
                             event_id=agreement.event_id)
            return None
        else:
            self.print_error('No person found for agreement {}'.format(agreement), event_id=agreement.event_id)
            return None

