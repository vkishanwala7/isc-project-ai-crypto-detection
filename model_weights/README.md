# model_weights/

* `veriframe_effb0_safl.pt` — EfficientNet-B0 checkpoint v2.1 trained by this project (see docs/AI_MODEL_CARD.md). Trained partly on team members' webcam faces (with consent) — keep it within the team.
  Included in the project archive for the team's academic use; git-ignored by default. Because the training
  data includes CelebA-derived images (non-commercial research terms), do not redistribute it publicly or use it commercially.
* `metrics.json`, `training_log.json`, `test_predictions.csv`, `team_holdout.json`, `robustness.json` — artefacts of the v2.1 training; `v1/` and `v2.0/` keep the metrics of earlier versions.
* `pretrained/efficientnet_b0_ra-3dd342df.pth` — ImageNet initialisation (timm, Apache-2.0), only needed to retrain.
  Download: https://github.com/rwightman/pytorch-image-models/releases/download/v0.1-weights/efficientnet_b0_ra-3dd342df.pth
