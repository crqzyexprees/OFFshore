import json
from datetime import date

import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.processors import TemplateProcessing

from backend import prediction
from backend.prediction import MAX_TOKENS, NUMBERS, FEATURE_VERSION, NoModel, encode, load, to_category

VOCAB = {"[PAD]": 0, "[UNK]": 1, "[CLS]": 2, "[SEP]": 3, "whole": 4, "foods": 5, "market": 6}


def bert_like_tokenizer() -> Tokenizer:
    tok = Tokenizer(WordLevel(VOCAB, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    tok.post_processor = TemplateProcessing(
        single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 2), ("[SEP]", 3)]
    )
    return tok


def test_encoding_starts_with_cls_and_pads_to_a_fixed_length():
    e = encode(bert_like_tokenizer(), "WHOLE FOODS Market", 4250, "purchase", date(2026, 1, 15))
    assert e.input_ids[:5] == [2, 4, 5, 6, 3]
    assert len(e.input_ids) == len(e.attention_mask) == MAX_TOKENS
    assert e.attention_mask[:6] == [1, 1, 1, 1, 1, 0]
    assert set(e.input_ids[5:]) == {0}


def test_long_descriptions_keep_their_closing_sep():
    e = encode(bert_like_tokenizer(), "market " * 100, 100, "purchase", date(2026, 1, 15))
    assert e.input_ids[0] == 2 and e.input_ids[-1] == 3
    assert all(e.attention_mask)


def test_a_refund_is_encoded_as_negative_money():
    when = date(2026, 1, 15)
    purchase = encode(bert_like_tokenizer(), "x", 4250, "purchase", when).numbers
    refund = encode(bert_like_tokenizer(), "x", 4250, "refund", when).numbers
    assert len(purchase) == len(NUMBERS)
    assert refund[0] == -purchase[0] < 0
    assert purchase[1:] == refund[1:]


def test_numbers_stay_in_a_small_range():
    for when in (date(2026, 1, 5), date(2026, 12, 27)):
        n = encode(bert_like_tokenizer(), "x", 1_000_000_00, "purchase", when).numbers
        assert 0 <= n[1] <= 1 and 0 <= n[2] <= 1 and n[0] < 20


def test_labels_outside_the_curated_list_are_not_predictions():
    assert to_category("Dining", 0.7) == ("Dining", 0.7)
    assert to_category("Gas", 0.9) == ("Other", None)


def test_no_bundle_means_no_model(tmp_path):
    assert isinstance(load(tmp_path), NoModel)
    assert NoModel().predict("x", 100, "purchase", date(2026, 1, 1)) == ("Other", None)


def write_bundle(directory, feature_version=FEATURE_VERSION):
    """A bundle whose 'model' says Dining for money out and Gas (not a curated
    Category) for money back, from the sign of the first number."""
    import onnx
    from onnx import TensorProto, helper

    weights = helper.make_tensor("W", TensorProto.FLOAT, [len(NUMBERS), 2], [1, -1] + [0, 0] * (len(NUMBERS) - 1))
    graph = helper.make_graph(
        [helper.make_node("MatMul", ["numbers", "W"], ["logits"])],
        "tiny",
        [
            helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["batch", MAX_TOKENS]),
            helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["batch", MAX_TOKENS]),
            helper.make_tensor_value_info("numbers", TensorProto.FLOAT, ["batch", len(NUMBERS)]),
        ],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["batch", 2])],
        initializer=[weights],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 14)])
    model.ir_version = 8
    onnx.save(model, directory / "classifier.onnx")
    bert_like_tokenizer().save(str(directory / "tokenizer.json"))
    (directory / "bundle.json").write_text(json.dumps({"feature_version": feature_version, "labels": ["Dining", "Gas"]}))


def test_a_model_bundle_predicts_through_the_shared_encoding(tmp_path):
    write_bundle(tmp_path)
    predictor = load(tmp_path)
    assert isinstance(predictor, prediction.OnnxPredictor)

    category, confidence = predictor.predict("whole foods", 4250, "purchase", date(2026, 1, 15))
    assert category == "Dining" and 0.5 < confidence <= 1
    assert predictor.predict("whole foods", 4250, "refund", date(2026, 1, 15)) == ("Other", None)


def test_a_bundle_trained_on_other_features_is_refused(tmp_path, capsys):
    write_bundle(tmp_path, feature_version=FEATURE_VERSION - 1)
    assert isinstance(load(tmp_path), NoModel)
    assert "retrain" in capsys.readouterr().err
