from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities.engine import OperatorConfig
import spacy
from presidio_analyzer.nlp_engine import SpacyNlpEngine

nlp = spacy.load("en_core_web_sm")


# Create a class inheriting from SpacyNlpEngine
class LoadedSpacyNlpEngine(SpacyNlpEngine):
    def __init__(self, loaded_spacy_model):
        super().__init__()
        self.nlp = {"en": loaded_spacy_model}


loaded_nlp_engine = LoadedSpacyNlpEngine(loaded_spacy_model=nlp)

anonymise_engine = AnonymizerEngine()
analyse_engine = AnalyzerEngine(nlp_engine=loaded_nlp_engine)


def analyse(query):
    """Given a query string, analyse for PII and return analysis results."""

    results = analyse_engine.analyze(
        text=query, entities=["PHONE_NUMBER", "PERSON", "EMAIL_ADDRESS"], language="en"
    )
    return results


def redact(query, results):
    """Given a query string, return a de-identified version of the query."""

    redacted = anonymise_engine.anonymize(
        text=query,
        analyzer_results=results,
        operators={
            "PERSON": OperatorConfig(
                "replace", {"new_value": "John Doe (client name redacted)"}
            ),
            "PHONE_NUMBER": OperatorConfig(
                "replace", {"new_value": "555-555-5555 (phone number redacted)"}
            ),
            "EMAIL_ADDRESS": OperatorConfig(
                "replace", {"new_value": "example@email.com (email redacted)"}
            ),
        },
    )

    return redacted.text
