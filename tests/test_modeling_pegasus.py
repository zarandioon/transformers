import unittest

from transformers import AutoConfig, AutoTokenizer, is_torch_available
from transformers.configuration_pegasus import max_gen_length, max_model_length
from transformers.file_utils import cached_property
from transformers.testing_utils import require_torch, slow, torch_device

from .test_modeling_bart import PGE_ARTICLE
from .test_modeling_mbart import AbstractSeq2SeqIntegrationTest


if is_torch_available():
    from transformers import AutoModelForSeq2SeqLM

XSUM_ENTRY_LONGER = """ The London trio are up for best UK act and best album, as well as getting two nominations in the best song category."We got told like this morning 'Oh I think you're nominated'", said Dappy."And I was like 'Oh yeah, which one?' And now we've got nominated for four awards. I mean, wow!"Bandmate Fazer added: "We thought it's best of us to come down and mingle with everyone and say hello to the cameras. And now we find we've got four nominations."The band have two shots at the best song prize, getting the nod for their Tynchy Stryder collaboration Number One, and single Strong Again.Their album Uncle B will also go up against records by the likes of Beyonce and Kanye West.N-Dubz picked up the best newcomer Mobo in 2007, but female member Tulisa said they wouldn't be too disappointed if they didn't win this time around."At the end of the day we're grateful to be where we are in our careers."If it don't happen then it don't happen - live to fight another day and keep on making albums and hits for the fans."Dappy also revealed they could be performing live several times on the night.The group will be doing Number One and also a possible rendition of the War Child single, I Got Soul.The charity song is a  re-working of The Killers' All These Things That I've Done and is set to feature artists like Chipmunk, Ironik and Pixie Lott.This year's Mobos will be held outside of London for the first time, in Glasgow on 30 September.N-Dubz said they were looking forward to performing for their Scottish fans and boasted about their recent shows north of the border."We just done Edinburgh the other day," said Dappy."We smashed up an N-Dubz show over there. We done Aberdeen about three or four months ago - we smashed up that show over there! Everywhere we go we smash it up!" """


@require_torch
class PegasusXSUMIntegrationTest(AbstractSeq2SeqIntegrationTest):
    checkpoint_name = "google/pegasus-xsum"
    src_text = [PGE_ARTICLE, XSUM_ENTRY_LONGER]
    tgt_text = [
        "California's largest electricity provider has turned off power to tens of thousands of customers.",
        "N-Dubz have revealed they weren't expecting to get four nominations at this year's Mobo Awards.",
    ]

    @cached_property
    def model(self):
        return AutoModelForSeq2SeqLM.from_pretrained(self.checkpoint_name).to(torch_device)

    @slow
    def test_pegasus_xsum_summary(self):
        assert self.tokenizer.model_max_length == 512
        inputs = self.tokenizer(self.src_text, return_tensors="pt", truncation=True, max_length=512, padding=True).to(
            torch_device
        )
        assert inputs.input_ids.shape == (2, 421)
        translated_tokens = self.model.generate(**inputs)
        decoded = self.tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)
        self.assertEqual(self.tgt_text, decoded)

        if "cuda" not in torch_device:
            return
        # Demonstrate fp16 issue, Contributions welcome!
        self.model.half()
        translated_tokens_fp16 = self.model.generate(**inputs, max_length=10)
        decoded = self.tokenizer.batch_decode(translated_tokens_fp16, skip_special_tokens=True)
        bad_fp16_result = ["unk_7unk_7unk_7unk_7unk_7unk_7unk_7", "unk_7unk_7unk_7unk_7unk_7unk_7unk_7"]
        self.assertListEqual(decoded, bad_fp16_result)


class PegasusConfigTests(unittest.TestCase):
    def test_all_config_max_lengths(self):
        failures = []
        pegasus_prefix = "google/pegasus"
        for dataset, max_len in max_gen_length.items():
            mname = f"{pegasus_prefix}-{dataset}"
            cfg = AutoConfig.from_pretrained(mname)

            if cfg.max_length != max_len:
                failures.append(f"config for {mname} had max_length: {cfg.max_length}, expected {max_len}")

            if cfg.max_position_embeddings < max_model_length[dataset]:
                # otherwise you get IndexError for e.g. position 513
                # see https://github.com/huggingface/transformers/issues/6599
                failures.append(
                    f"config for {mname} had max_position_embeddings: {cfg.max_position_embeddings}, expected {max_model_length[dataset]}"
                )

            tokenizer = AutoTokenizer.from_pretrained(mname)
            if max_model_length[dataset] != tokenizer.model_max_length:
                failures.append(
                    f"tokenizer.model_max_length {tokenizer.model_max_length} expected {max_model_length[dataset]}"
                )

        if failures == []:
            return
        # error
        all_fails = "\n".join(failures)
        raise AssertionError(f"The following configs have unexpected settings: {all_fails}")
