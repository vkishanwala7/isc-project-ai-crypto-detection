import { useQuery } from "@tanstack/react-query";
import { Brain } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../lib/api";
import { pct } from "../lib/format";
import { Chip, EmptyState, ErrorNote, Hash, KV, PageHeader, Panel, Skeleton, cx } from "../components/ui";

const FAMILY: Record<string, string> = {
  celeba_real: "CelebA (real)", celebdf_frame_real: "Celeb-DF frames (real)", dfl_source_real: "DFL source frames (real)",
  faceapp_on_celeba: "FaceApp edits of CelebA", faceapp: "FaceApp (other)", stylegan_tpdne: "StyleGAN (thispersondoesnotexist)",
  deepfacelab: "DeepFaceLab face swaps", dalle: "DALL·E 2/3 faces",
  team_webcam_real: "Team webcam (real)", celebdf_video_real: "Real interview videos (Celeb-DF frames)", avatarify_video: "Avatarify deepfake videos", deepfacelab_video: "DeepFaceLab deepfake videos",
};

const ROBUST: Record<string, string> = {
  none: "None (reference)", jpeg_q70: "JPEG quality 70", jpeg_q40: "JPEG quality 40",
  downscale_112: "Downscale to 112 px and back", downscale_64: "Downscale to 64 px and back", "blur_r1.5": "Gaussian blur, radius 1.5",
};

export default function ModelLab() {
  const info = useQuery({ queryKey: ["model-info"], queryFn: api.modelInfo });
  const met = useQuery({ queryKey: ["model-metrics"], queryFn: api.modelMetrics });
  if (info.isLoading || met.isLoading) return <div className="space-y-4"><Skeleton className="h-20" /><Skeleton className="h-[400px]" /></div>;
  if (info.isError) return <ErrorNote message={(info.error as Error).message} onRetry={() => info.refetch()} />;
  const i = info.data;
  const m = met.data;
  const t = m?.available ? m.test : null;
  const cm = t?.confusion_matrix;
  const log = (i.training?.epochs_log ?? []) as { epoch: number; train_loss: number; val_loss: number; val_auc: number; val_acc: number }[];

  return (
    <div className="space-y-6">
      <PageHeader title="Model & dataset"
        lede="What the AI dimension actually is: the checkpoint, how it was trained, and how it performed on a held-out test split it never saw. Metrics are read from files produced by the training run." />

      {!i.available ? (
        <EmptyState icon={<Brain className="size-6" />} title="Model weights unavailable">{i.reason}</EmptyState>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
          <Panel channel="signal" title={<span className="flex items-center gap-2">{i.name} <Chip tone="signal">v{i.version}</Chip><Chip tone="ok">Trained by this project</Chip></span>}
            description="Stage 1: fine-tuned from ImageNet weights on face crops from SAFL images and video frames. Stage 2: fine-tuned on real webcam clips of three team members, with a fourth person held out for testing. CPU only, fixed seed.">
            <KV rows={[
              ["Architecture", i.architecture],
              ["Checkpoint", <span className="mono text-[12px]">{i.checkpoint_file}</span>],
              ["Checkpoint SHA-256", <Hash value={i.checkpoint_sha256} label="checkpoint SHA-256" small />],
              ["Initial weights", i.training?.init_weights],
              ["Face detector", i.preprocessing.face_detector],
              ["Crop", i.preprocessing.crop],
              ["Normalisation", i.preprocessing.normalisation],
              ["Decision threshold", <span><span className="mono">{i.threshold}</span> (chosen on validation by Youden's J), inconclusive band ±0.10</span>],
              ["Calibration", <span>Temperature scaling, T = <span className="mono">{i.temperature}</span> (fitted on validation)</span>],
              ["Aggregation", `Images: ${i.decision.image_aggregation}. Videos: ${i.decision.video_aggregation}.`],
              ["Training", i.training ? `${i.training.epochs} epochs, ${i.training.optimizer}, ${i.training.schedule}, max LR ${i.training.max_lr}, batch ${i.training.batch_size}, ${i.training.loss}; ${i.training.hardware}; ${Math.round(i.training.total_seconds / 60)} min` : "—"],
              ["Augmentation", i.training?.augmentations],
              ...(i.training?.stage2 ? [["Stage 2", `${i.training.stage2.epochs} epochs from v2.0, LR ${i.training.stage2.lr}, ${i.training.stage2.team_train_crops} webcam face crops of people ${i.training.stage2.team_people_train.join(", ")} (with consent), mixed with ${i.training.stage2.safl_subset} SAFL crops; person ${i.training.stage2.team_holdout} never used for training`] as [string, string]] : []),
            ]} />
          </Panel>
          <Panel title="Training curve (stage 1)" description="Per-epoch validation results on SAFL; the best validation ROC-AUC epoch was kept. Stage 2 fine-tuning is listed under Training details.">
            {log.length ? (
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={log} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#e6eaf0" vertical={false} />
                    <XAxis dataKey="epoch" tick={{ fontSize: 11, fill: "#5a6779" }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#5a6779" }} tickLine={false} axisLine={false} domain={[0, "auto"]} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #dce2ea", fontSize: 12 }} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                    <Line dataKey="val_auc" name="Val ROC-AUC" stroke="#0a8c99" strokeWidth={2} dot={{ r: 3 }} />
                    <Line dataKey="val_acc" name="Val accuracy@0.5" stroke="#5b4bc4" strokeWidth={2} dot={{ r: 3 }} />
                    <Line dataKey="train_loss" name="Train loss" stroke="#8592a3" strokeDasharray="4 3" dot={false} />
                    <Line dataKey="val_loss" name="Val loss" stroke="#0e1726" strokeDasharray="4 3" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : <p className="text-sm text-muted">No training log found.</p>}
          </Panel>
        </div>
      )}

      <Panel title="Held-out test results" description={m?.available ? m.computed_on : undefined}>
        {!m?.available ? <EmptyState title="No evaluation available">{m?.message}</EmptyState> : (
          <div className="grid gap-8 lg:grid-cols-[1fr_auto]">
            <div>
              <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
                {[
                  ["ROC-AUC", t.roc_auc.toFixed(3)], ["PR-AUC", t.pr_auc.toFixed(3)], ["Accuracy", pct(t.accuracy)], ["Balanced acc.", pct(t.balanced_accuracy)],
                  ["Precision", pct(t.precision)], ["Recall", pct(t.recall)], ["Specificity", pct(t.specificity)], ["F1", t.f1.toFixed(3)],
                ].map(([k, v]) => (
                  <div key={k} className="bg-surface px-4 py-3"><p className="text-[12px] text-muted">{k}</p><p className="mono mt-0.5 text-[20px] font-medium">{v}</p></div>
                ))}
              </div>
              <p className="mt-3 text-[12.5px] text-muted">
                n = {m.n_test} ({m.n_test_real} real, {m.n_test_fake} manipulated), threshold {m.threshold}. Expected calibration error after temperature scaling: {m.ece_test_calibrated}.
              </p>
              <h3 className="mt-6 mb-2 text-[13px] font-medium">Accuracy by source family (test split)</h3>
              <ul className="space-y-1.5">
                {Object.entries(m.per_source_family_test_accuracy as Record<string, { n: number; accuracy: number; label: string }>).sort((a, b) => b[1].n - a[1].n).map(([k, v]) => (
                  <li key={k} className="grid grid-cols-[minmax(0,1fr)_60px_56px] items-center gap-3 text-[12.5px]">
                    <span className="truncate">{FAMILY[k] ?? k} <span className="text-faint">({v.label}, n={v.n})</span></span>
                    <div className="h-1.5 rounded-full bg-paper"><div className={cx("h-full rounded-full", v.label === "real" ? "bg-ok" : "bg-signal")} style={{ width: `${v.accuracy * 100}%` }} /></div>
                    <span className="mono text-right">{pct(v.accuracy)}</span>
                  </li>
                ))}
              </ul>
              {Object.values(m.per_source_family_test_accuracy as Record<string, { n: number }>).some((v) => v.n < 10) && <p className="mt-2 text-[12px] text-faint">Families with fewer than 10 test images give unreliable percentages.</p>}
              {m.video_level_test && (
                <div className="mt-6 rounded-xl border border-line p-4">
                  <h3 className="text-[13px] font-medium">Whole-video results ({m.video_level_test.n_videos} held-out videos)</h3>
                  <p className="mt-0.5 text-[12px] text-muted">Each video's score is the mean of its frame scores, at the deployed threshold. No frame of these videos was used for training.</p>
                  <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[12.5px]">
                    <span>Accuracy <span className="mono font-medium">{pct(m.video_level_test.accuracy)}</span></span>
                    <span>Real videos correct <span className="mono font-medium">{pct(m.video_level_test.specificity)}</span></span>
                    <span>Deepfake videos caught <span className="mono font-medium">{pct(m.video_level_test.recall)}</span></span>
                    <span>ROC-AUC <span className="mono font-medium">{m.video_level_test.roc_auc.toFixed(3)}</span></span>
                  </div>
                </div>
              )}
            </div>
            <div>
              <h3 className="mb-2 text-[13px] font-medium">Confusion matrix</h3>
              <table className="text-[13px]" aria-label="Confusion matrix">
                <thead><tr><th /><th colSpan={2} className="pb-1 text-[12px] font-normal text-muted">Predicted</th></tr>
                  <tr><th /><th className="px-3 pb-1 text-[12px] font-medium">Real</th><th className="px-3 pb-1 text-[12px] font-medium">Manip.</th></tr></thead>
                <tbody>
                  <tr><th className="pr-3 text-right text-[12px] font-medium">Actual real</th><Cell v={cm.tn} good /><Cell v={cm.fp} /></tr>
                  <tr><th className="pr-3 text-right text-[12px] font-medium">Actual manip.</th><Cell v={cm.fn} /><Cell v={cm.tp} good /></tr>
                </tbody>
              </table>
              <p className="mt-2 max-w-[28ch] text-[12px] text-muted">{cm.fp} authentic face{cm.fp === 1 ? "" : "s"} wrongly flagged; {cm.fn} manipulated face{cm.fn === 1 ? "" : "s"} missed.</p>
            </div>
          </div>
        )}
      </Panel>

      {m?.team_holdout && (
        <Panel channel="signal" title="Unseen person on a normal webcam" description={`Person ${m.team_holdout.person} was recorded on the same laptop webcam but never used for training. This is the closest test we have of how the model treats a new, ordinary face.`}>
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
            <p><span className="mono text-[26px] font-medium">{Math.round(m.team_holdout.frames_flagged_rate * m.team_holdout.n_frames)}/{m.team_holdout.n_frames}</span> <span className="text-[13px] text-muted">frames wrongly flagged</span></p>
            <p><span className="mono text-[26px] font-medium">{m.team_holdout.frame_score_median.toFixed(3)}</span> <span className="text-[13px] text-muted">median score (threshold {m.threshold})</span></p>
          </div>
          <ul className="mt-3 space-y-1 text-[12.5px] text-muted">
            {Object.entries(m.team_holdout.per_media as Record<string, { n: number; mean: number; flagged: boolean }>).map(([k, v]) => (
              <li key={k}>{k.endsWith(".mp4") ? "Webcam clip" : "Webcam photo"} <span className="mono">{k}</span>: mean score <span className="mono text-ink">{v.mean.toFixed(3)}</span> over {v.n} frame{v.n === 1 ? "" : "s"}, {v.flagged ? "flagged" : "not flagged"}</li>
            ))}
          </ul>
          <p className="mt-3 text-[12px] text-faint">Only one held-out person, one room and one camera: a useful sanity check, not a demographic benchmark.</p>
        </Panel>
      )}

      {m?.robustness && (
        <Panel title="Robustness check" description={`${m.robustness.note} Perturbations are applied to the same held-out crops; this measures sensitivity, not real-world accuracy.`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[13px]">
              <thead className="text-[12px] text-muted"><tr className="border-b border-line"><th className="py-2 font-medium">Perturbation</th><th className="font-medium">Accuracy</th><th className="font-medium">Recall (manip.)</th><th className="font-medium">Specificity (real)</th><th className="font-medium">ROC-AUC</th><th className="font-medium">False positives</th></tr></thead>
              <tbody>
                {Object.entries(m.robustness.results as Record<string, { accuracy: number; recall: number; specificity: number; roc_auc: number; confusion_matrix: { fp: number } }>).map(([k, r]) => (
                  <tr key={k} className="border-b border-line/70">
                    <td className="py-2 font-medium">{ROBUST[k] ?? k}</td>
                    <td className="mono">{pct(r.accuracy)}</td><td className="mono">{pct(r.recall)}</td>
                    <td className={cx("mono", r.specificity < 0.8 && "text-bad")}>{pct(r.specificity)}</td>
                    <td className="mono">{r.roc_auc.toFixed(3)}</td><td className="mono">{r.confusion_matrix.fp}/{m.n_test_real}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 max-w-[90ch] text-[12.5px] leading-relaxed text-muted">Compression and moderate blur or downscaling now cost only a few points. Very low resolution (64 px faces) still makes about a third of real faces look manipulated, so tiny or heavily resized faces remain out of scope. Our first model failed much worse here: with blur, only 17% of real faces were judged correctly, against 77% now.</p>
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Dataset" description="Chosen after comparing alternatives; see docs/DATASET_RESEARCH.md.">
          <KV rows={[
            ["Name", i.dataset.name],
            ["Source", <a className="text-signal hover:underline" href={i.dataset.source} target="_blank" rel="noreferrer">{i.dataset.source}</a>],
            ["Commit", <span className="mono text-[12px]">{i.dataset.commit}</span>],
            ["Licence", i.dataset.license],
            ["Split", i.training ? `${i.training.split_sizes.train} train / ${i.training.split_sizes.val} val / ${i.training.split_sizes.test} test face crops (images grouped by near-duplicates, video frames grouped by video), plus our own webcam clips split by person` : "—"],
            ["Class balance (train)", i.training ? `${i.training.train_real} real / ${i.training.train_fake} manipulated; loss re-weighted (pos_weight ${i.training.pos_weight.toFixed(3)})` : "—"],
          ]} />
        </Panel>
        <Panel title="Limitations you should state out loud">
          <ul className="list-disc space-y-2 pl-5 text-[13px] leading-relaxed text-ink/85">
            <li>Real training faces are mostly celebrities (CelebA photos, YouTube interviews) plus three team members on one webcam. Other demographics, ages, rooms and cameras are only lightly covered, so an unfamiliar real face can still be flagged.</li>
            <li>Teaching the model our webcam made it slightly stricter on some CelebA-style photos: their specificity fell from 95% (v2.0) to 90%. We chose this trade-off because ordinary camera faces matter more for real use.</li>
            <li>Unseen generators (new diffusion models, new face-swap tools) and heavy recompression degrade accuracy; very low resolution still causes false positives (see the robustness check).</li>
            <li>Subtle edits are hard: FaceApp edits of real faces are caught only about 72% of the time. Fully generated faces (StyleGAN, DALL·E) are caught far more reliably.</li>
            <li>SAFL has no identity labels, so its split cannot guarantee a celebrity never appears in both train and test (video frames are kept per video; team data is split per person).</li>
            <li>Video analysis samples frames independently; temporal artefacts and audio are not analysed.</li>
            <li>Test metrics come from one split of one dataset. They are not a benchmark against published detectors.</li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}

function Cell({ v, good }: { v: number; good?: boolean }) {
  return <td className={cx("mono size-20 rounded-md text-center text-[18px] font-medium", good ? "bg-signal-wash text-signal" : "bg-bad-wash text-bad")}>{v}</td>;
}
