from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider


def create_analyzer() -> AnalyzerEngine:
    # Ép Presidio dùng spaCy + en_core_web_sm (nhẹ, không tải 400MB)
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [
            {"lang_code": "en", "model_name": "en_core_web_sm"},
        ],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
    return AnalyzerEngine(nlp_engine=nlp_engine)


def main():
    analyzer = create_analyzer()

    tests = [
        ("My email is alice@example.com and my phone number is +1-202-555-0199", "en"),
        ("Số điện thoại của tôi là 0987 654 321", "en"),
        ("My credit card is 4111 1111 1111 1111", "en"),
        ("My SSN is 123-45-6789", "en"),
    ]

    for text, lang in tests:
        print("=" * 80)
        print("TEXT:", text)
        results = analyzer.analyze(text=text, language=lang)
        for r in results:
            frag = text[r.start : r.end]
            print(
                f"- {r.entity_type:<16} score={r.score:<4} span=({r.start},{r.end}) text={frag!r}"
            )


if __name__ == "__main__":
    main()