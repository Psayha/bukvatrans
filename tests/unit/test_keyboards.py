"""Tests for inline keyboard builders."""
from src.bot.keyboards.inline import (
    transcription_result_kb,
    subscribe_kb,
    topup_kb,
    language_kb,
)


class TestTranscriptionResultKb:
    def test_contains_summary_button(self):
        kb = transcription_result_kb("abc-123")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in all_buttons]
        assert any("summary:abc-123" in c for c in callbacks)

    def test_contains_docx_button(self):
        kb = transcription_result_kb("abc-123")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in all_buttons]
        assert any("docx:abc-123" in c for c in callbacks)

    def test_srt_button_only_for_video(self):
        kb_no_video = transcription_result_kb("abc-123", has_video=False)
        kb_video = transcription_result_kb("abc-123", has_video=True)

        def has_srt(kb):
            return any(
                "srt:" in btn.callback_data
                for row in kb.inline_keyboard
                for btn in row
            )

        assert not has_srt(kb_no_video)
        assert has_srt(kb_video)

    def test_transcription_id_in_callbacks(self):
        tid = "unique-id-999"
        kb = transcription_result_kb(tid)
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert all(tid in cb for cb in all_cbs if cb)


class TestSubscribeKb:
    def test_has_all_plans(self):
        kb = subscribe_kb()
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert any("plan:basic_monthly" in c for c in all_cbs)
        assert any("plan:basic_yearly" in c for c in all_cbs)
        assert any("plan:pro_monthly" in c for c in all_cbs)
        assert any("plan:pro_yearly" in c for c in all_cbs)


class TestTopupKb:
    def test_has_all_topup_options(self):
        kb = topup_kb()
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert any("topup:topup_99" in c for c in all_cbs)
        assert any("topup:topup_299" in c for c in all_cbs)
        assert any("topup:topup_499" in c for c in all_cbs)

    def test_has_back_button(self):
        kb = topup_kb()
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert any("topup:back" in c for c in all_cbs)


class TestLanguageKb:
    def test_has_russian(self):
        kb = language_kb()
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert any("lang:ru" in c for c in all_cbs)

    def test_has_english(self):
        kb = language_kb()
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert any("lang:en" in c for c in all_cbs)

    def test_has_auto(self):
        kb = language_kb()
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert any("lang:auto" in c for c in all_cbs)
