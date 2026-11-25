"""Exploratory confirmed input; experimental source review remains pending."""
from pathlib import Path
from adroit.experiments.anomaly import RecordSearch
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.anomaly_intake import readiness

class ConfirmedAnomalySearch(RecordSearch):
    """A record search built from a confirmed anomaly interpretation in the experimental catalog, with its current
    source review if one exists."""
    interpretation_confirmed=True

    def __init__(self,reference: str):
        self.catalog=ExperimentalCatalog()
        self.confirmation=readiness(reference,self.catalog)
        self.revision=self.catalog.load(self.confirmation.interpretation.revision)
        super().__init__(self.confirmation.interpretation.record,key=self.confirmation.confirmation_id)
        from adroit.constraints.experimental_review import current_review
        self.review=current_review(self.revision.reference,self.confirmation.interpretation.result_id,self.catalog)

    @property
    def verified(self):
        """Whether a complete current source review covers the result."""
        return self.review is not None

    @property
    def info(self):
        """The record's info, its data pointing at the confirmation file, with a note saying whether the source
        values were reviewed."""
        value=super().info
        data=[d.model_copy(update={'path':str(self.catalog.path(f'confirmations/{self.confirmation.confirmation_id}.json'))}) for d in value.data]
        return value.model_copy(update={'data':data,'validation_note':
            ('Selected source values reviewed; ' if self.review else 'Source review pending; ')+
            'fidelity-B reconstruction, not an official likelihood validation.'})

    def evidence(self) -> dict:
        """The confirmation, the dossier revision and the source review (None while pending), with the scope of the
        reconstruction."""
        return {'confirmation':self.confirmation.model_dump(mode='json'),'dossier':self.revision.model_dump(mode='json'),
                'source_review':self.review.model_dump(mode='json') if self.review else None,
                'scope':('selected source values reviewed; ' if self.review else 'source review pending; ')+
                        'confirmed fidelity-B reconstruction, not official likelihood validation'}

    def input_files(self) -> list[Path]:
        """The catalog files the module rests on: the review (if any), the confirmation and the dossier revision."""
        return ([self.catalog.path(f'reviews/{self.review.review_id}.json')] if self.review else [])+[
                self.catalog.path(f'confirmations/{self.confirmation.confirmation_id}.json'),
                self.catalog.path(f'experiments/{self.revision.experiment_id}/{self.revision.revision_id}.json')]
