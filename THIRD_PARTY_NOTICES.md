# Third-Party Notices

This service redistributes third-party software and model weights inside its
Docker image. The notices below are provided as required by the applicable
licences.

## 1. Kokoro TTS model weights

- **Component:** `hexgrad/Kokoro-82M` (Kokoro v1.0)
- **Licence:** Apache License 2.0
- **Source:** https://huggingface.co/hexgrad/Kokoro-82M
- **Architecture:** StyleTTS 2 (https://arxiv.org/abs/2306.07691) with an
  ISTFTNet decoder (https://arxiv.org/abs/2203.02395), architected by
  Li et al. (https://github.com/yl4579/StyleTTS2)
- **Declared base model:** `yl4579/StyleTTS2-LJSpeech`
- **Parameters:** 82 million
- **Revision used by this service:** `f3ff3571791e39611d31c381e3a41a3af07b4987`
- **Weights SHA256:** `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4`
- **Copyright:** the Kokoro authors. See the model card for the full author list.

The weights are downloaded at image build time from the Hugging Face Hub and
cached inside the image. The Apache-2.0 text is bundled at
[`licenses/LICENSE-2.0.txt`](licenses/LICENSE-2.0.txt).

### Training-data attribution (CC BY)

The Kokoro model card lists the following Creative Commons Attribution audio
included in its training data. The attribution is reproduced here as required
by those licences:

| Audio data | Duration used | Licence |
| --- | --- | --- |
| [Koniwa](https://github.com/koniwa/koniwa) `tnc` | < 1 h | CC BY 3.0 |
| [SIWIS](https://datashare.ed.ac.uk/handle/10283/2353) | < 11 h | CC BY 4.0 |

The model card states that Kokoro v1.0 was trained on a few hundred hours of
public-domain, permissively licensed and synthetic audio.

## 2. Python packages

| Package | Version | Licence |
| --- | --- | --- |
| [kokoro](https://github.com/hexgrad/kokoro) | 0.9.4 | Apache-2.0 |
| [misaki](https://github.com/hexgrad/misaki) | 0.9.4 | Apache-2.0 |
| [transformers](https://github.com/huggingface/transformers) | 5.17.0 | Apache-2.0 |
| [huggingface-hub](https://github.com/huggingface/huggingface_hub) | 1.33.0 | Apache-2.0 |
| [spacy](https://github.com/explosion/spacy) | 3.8.16 | MIT |
| [en_core_web_sm](https://github.com/explosion/spacy-models) | 3.8.0 | MIT |
| [soundfile](https://github.com/python-soundfile/soundfile) | 0.14.0 | BSD-3-Clause |
| [numpy](https://github.com/numpy/numpy) | 2.5.3 | BSD-3-Clause |
| [fastapi](https://github.com/tiangolo/fastapi) | 0.141.1 | MIT |
| [uvicorn](https://github.com/encode/uvicorn) | 0.54.0 | BSD-3-Clause |
| [pydantic](https://github.com/pydantic/pydantic) | 2.13.5 | MIT |
| [torch](https://github.com/pytorch/pytorch) | 2.14.0 (CPU) | BSD-3-Clause |

Full licence texts for the packages above are distributed inside their own
wheels/containers; the Apache-2.0 text covering Kokoro, misaki and the model
weights is bundled in `licenses/`.

## 3. This service

No licence has been chosen for the service code in this repository. Add a
`LICENSE` file before distributing it. Nothing here overrides the terms of the
components listed above.
