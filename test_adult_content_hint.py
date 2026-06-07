"""Tests for adult content hint heuristics."""

import config


def test_is_clearly_adult_content_negative():
    assert config.is_clearly_adult_content("") is False
    assert config.is_clearly_adult_content("男主会催眠术") is False
    assert config.is_clearly_adult_content("轻轻握了握手") is False
    assert config.is_clearly_adult_content("进入房间调查") is False
    assert config.is_clearly_adult_content("解开谜题") is False
    assert config.is_clearly_adult_content("扑倒在地格挡") is False
    assert config.is_clearly_adult_content("插入线索到报告") is False
    assert config.is_clearly_adult_content("亲吻她的脸颊告别") is False
    assert config.is_clearly_adult_content("拥抱她道别") is False
    assert config.is_clearly_adult_content("解开扣子整理衣领") is False


def test_is_clearly_adult_content_explicit_phrase():
    assert config.is_clearly_adult_content("两人发生了性行为") is True


def test_is_clearly_adult_content_strong_phrases():
    assert config.is_clearly_adult_content("解开衣扣深吻，手探入衣内抚摸") is True


def test_suggest_adult_mode_for_options():
    opts = [
        "调查线索→推进主线|冷静|无",
        "把她按在墙边深吻，解开衣扣抚摸→情欲升温|欲望|艾莉丝 affection+3",
    ]
    assert config.suggest_adult_mode_for_options(opts) is True
    assert config.suggest_adult_mode_for_options(["前往图书馆查资料"]) is False
    assert config.suggest_adult_mode_for_options(["进入地下城", "解开机关谜题"]) is False
