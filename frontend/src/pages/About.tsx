import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { EvidenceMatrix } from "../components/evidence";
import { PageHeader, Panel } from "../components/ui";

const TEAM = [
  ["Alakh Bathani", "U24AI102"],
  ["Krishna Baheti", "U24AI133"],
  ["Divam Shah", "U24AI076"],
  ["Vivaan Kishanwala", "U24AI114"],
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <Panel title={title}><div className="max-w-[78ch] space-y-3 text-[14px] leading-[1.7] text-ink/85">{children}</div></Panel>
    </section>
  );
}

export default function About() {
  const loc = useLocation();
  useEffect(() => { if (loc.hash) document.getElementById(loc.hash.slice(1))?.scrollIntoView(); }, [loc.hash]);
  return (
    <div className="grid gap-8 lg:grid-cols-[200px_minmax(0,1fr)]">
      <nav aria-label="On this page" className="no-print sticky top-24 hidden self-start text-[13px] lg:block">
        <ul className="space-y-1.5 border-l border-line pl-4 text-muted">
          {[["architecture", "Architecture"], ["ai", "The AI model"], ["hashes", "Hashes"], ["signatures", "Digital signatures"], ["c2pa", "C2PA"], ["trust", "Trust model"], ["phash", "pHash limits"], ["evidence", "Combining evidence"], ["threats", "Threat model"], ["limits", "Known limitations"], ["refs", "References"], ["team", "Team"]].map(([id, t]) => (
            <li key={id}><a href={`#${id}`} className="hover:text-ink">{t}</a></li>
          ))}
        </ul>
      </nav>
      <div className="space-y-6">
        <PageHeader title="About & methodology" lede="VERIFRAME is an Information Security & Cryptography course project by Team 16. It shows how AI media forensics and cryptographic provenance answer different questions, and why neither alone establishes truth." />

        <Section id="architecture" title="System architecture">
          <p>A React + TypeScript single-page app talks to a FastAPI backend over <code className="mono text-[13px]">/api</code>. The backend has four isolated services: <strong>media</strong> (magic-byte validation, safe decoding, SHA-256, pHash, private file storage), <strong>AI</strong> (MTCNN face detection and an EfficientNet-B0 classifier, run locally on CPU), <strong>provenance</strong> (C2PA via the official <code className="mono text-[13px]">c2pa-python</code> SDK, plus a detached Ed25519 envelope), and <strong>audit</strong>. Cases, assets, analyses, provenance records and audit events persist in SQLite. No media is sent to third-party services.</p>
          <pre className="mono overflow-x-auto rounded-lg bg-ink p-4 text-[12px] leading-relaxed text-white/85">{`Browser ──▶ /api/analyze ──▶ validate → hash → store
                               ├─▶ AI: faces → EfficientNet-B0 → calibrated score   (signal channel)
                               └─▶ Provenance: C2PA reader → binding/signature/trust (seal channel)
                                          └─▶ evidence matrix (rule, not a score) → case + audit`}</pre>
        </Section>

        <Section id="ai" title="The AI model">
          <p>Faces are detected with MTCNN, cropped with a 30% margin and resized to 224×224. An EfficientNet-B0, initialised from ImageNet weights, was trained in this project in two stages. Stage 1 used the SAFL dataset: real CelebA photos and real interview videos, against FaceApp edits, StyleGAN faces, DeepFaceLab swaps, DALL·E faces and Avatarify deepfake videos, with augmentation that randomises sharpness, noise and compression so image quality is not mistaken for manipulation. Stage 2 added real webcam clips of three team members, because ordinary webcam faces were being wrongly flagged; a fourth member was kept out of training to test the fix. Scores are temperature-scaled and the threshold is chosen on a validation split. Test metrics on the Model & dataset page come from held-out data used only once.</p>
          <p>An image with no confidently detected face returns <em>inconclusive</em> with no score; the model is never applied to a whole scene it was not trained on. Videos are analysed by sampling up to 16 frames evenly and averaging the per-frame scores of frames that contain faces.</p>
        </Section>

        <Section id="hashes" title="SHA-256: exact-byte integrity">
          <p>SHA-256 maps any file to a 256-bit digest. It is deterministic and collision-resistant: changing a single byte changes roughly half of the output bits, and finding two different files with the same digest is computationally infeasible. A digest on its own proves nothing about <em>who</em> produced a file; it only lets you detect any change relative to a digest you already trust.</p>
        </Section>

        <Section id="signatures" title="Digital signatures">
          <p>A signature binds a statement to a private key. VERIFRAME's C2PA credentials use ECDSA P-256 with SHA-256 (ES256) inside a COSE signature; the educational envelope uses Ed25519. Verification needs only the public key or certificate. A valid signature shows that whoever controls the private key signed exactly this claim. Whether you should believe that signer is a separate question, answered by the trust model.</p>
        </Section>

        <Section id="c2pa" title="C2PA Content Credentials">
          <p>The C2PA specification defines a manifest embedded in the file (JUMBF), containing assertions (such as actions and the signing context) and a <em>hard binding</em>: a hash over the asset's bytes, excluding the manifest itself. The claim referencing those assertions is signed. Verification recomputes the hashes and checks the signature and the certificate chain.</p>
          <p>Browser captures are signed with the SDK's CREATE intent and the IPTC <em>digitalCapture</em> source type, plus a vendor assertion stating that the VERIFRAME demo service signed after browser capture with no hardware attestation. Uploads use the EDIT intent: the received bytes become the <em>parentOf</em> ingredient and a <em>c2pa.opened</em> action is recorded, so no claim is made about how the content was originally created.</p>
          <p>C2PA establishes whether provenance assertions are bound to the asset and validly signed under a trust policy. It makes no judgement about whether the scene is true.</p>
        </Section>

        <Section id="trust" title="Trust model">
          <p>VERIFRAME generates a local <em>Demo Root CA</em> and a <em>Demo Signer</em> certificate on first run. The verifier's local demo trust policy trusts only that root (plus any anchors you add). Signatures from the demo signer therefore show as trusted here and untrusted anywhere else; third-party Content Credentials show as cryptographically valid but untrusted unless you add their anchors. The demo signer is not on the official C2PA trust list. Private keys stay in <code className="mono text-[13px]">keys/</code> with 0600 permissions and never appear in API responses, the database or the browser.</p>
          <p>No RFC 3161 timestamp authority is used (the demo runs offline), so signing times are signer-asserted.</p>
        </Section>

        <Section id="phash" title="pHash is not integrity">
          <p>A perceptual hash summarises low-frequency image structure in 64 bits, so resized or recompressed copies stay within a small Hamming distance. That makes it useful for finding visually similar files. It is not collision-resistant, can be deliberately manipulated, and says nothing about whether bytes changed. VERIFRAME labels every pHash figure as a heuristic and never uses it for an integrity decision.</p>
        </Section>

        <section id="evidence" className="scroll-mt-24">
          <Panel title="Combining the evidence" description="The combined label is a deterministic lookup in this matrix, implemented in backend/app/services/evidence.py. There is no single numeric truth score.">
            <EvidenceMatrix />
            <ul className="mt-4 list-disc space-y-1.5 pl-5 text-[13.5px] leading-relaxed text-ink/85">
              <li>Missing provenance never produces a “fake” label.</li>
              <li>A failed integrity check is reported first, and the AI result is still shown separately.</li>
              <li>If the model is unavailable, provenance is reported alone and no AI score is fabricated.</li>
            </ul>
          </Panel>
        </section>

        <Section id="threats" title="Threat model (summary)">
          <ul className="list-disc space-y-1.5 pl-5">
            <li><strong>Malicious uploads and decompression bombs:</strong> magic-byte checks, size, pixel and duration caps, full decode in a guarded path, generated filenames, files served only by database id with <code className="mono text-[13px]">nosniff</code>.</li>
            <li><strong>File replacement and tampering:</strong> detected by the C2PA hard binding and the envelope's SHA-256.</li>
            <li><strong>Signature stripping:</strong> re-encoding removes embedded credentials; the result is “no provenance”, which is why absence is reported neutrally rather than as authenticity.</li>
            <li><strong>Metadata spoofing:</strong> unsigned metadata is never trusted; signed assertions are only as trustworthy as the signer.</li>
            <li><strong>Key theft or a compromised signer:</strong> keys are local, permission-restricted and rotatable; a stolen demo key would let an attacker sign anything, which is why trust policy matters.</li>
            <li><strong>Classifier evasion and domain shift:</strong> the AI result is labelled as a model estimate with known blind spots.</li>
            <li><strong>Misleading interpretation:</strong> separate dimensions, explicit wording, and a persistent disclaimer.</li>
          </ul>
          <p>The full version is in <code className="mono text-[13px]">docs/THREAT_MODEL.md</code>.</p>
        </Section>

        <Section id="limits" title="Known limitations">
          <p>This is a local academic demonstration, not a production forensic certification platform. The classifier is trained on a small dataset and will make mistakes, especially on unseen generators and compressed social-media media. Signing happens on the server after capture, so it cannot prove which camera produced the frames. The demo trust root is self-issued. WebM recordings cannot carry an embedded C2PA manifest with the installed SDK and receive only the detached envelope.</p>
        </Section>

        <Section id="refs" title="References and attribution">
          <ol className="list-decimal space-y-1.5 pl-5 text-[13px]">
            <li>Falcón-López, S. A. <em>Synthetic and Authentic Forensic Lab (SAFL) Dataset.</em> GitHub, oigres5/SAFL, CC BY 4.0. Underlying sources: CelebA (Liu et al., ICCV 2015) and Celeb-DF (Li et al., CVPR 2020) under their own terms.</li>
            <li>Tan, M. and Le, Q. V. EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks. ICML 2019.</li>
            <li>Wightman, R. PyTorch Image Models (timm), Apache-2.0; ImageNet weights <code className="mono">efficientnet_b0_ra-3dd342df</code>.</li>
            <li>Zhang, K. et al. Joint Face Detection and Alignment Using Multitask Cascaded Convolutional Networks. IEEE SPL 2016; implementation: facenet-pytorch (MIT).</li>
            <li>Guo, C. et al. On Calibration of Modern Neural Networks. ICML 2017 (temperature scaling).</li>
            <li>Coalition for Content Provenance and Authenticity. C2PA Technical Specification 2.5. spec.c2pa.org.</li>
            <li>Content Authenticity Initiative. c2pa-python (official Python bindings), MIT/Apache-2.0.</li>
            <li>NIST FIPS 180-4 (SHA-2); RFC 8032 (Ed25519); FIPS 186-5 (ECDSA).</li>
            <li>Zauner, C. Implementation and Benchmarking of Perceptual Image Hash Functions. 2010; implementation: imagehash.</li>
          </ol>
        </Section>

        <section id="team" className="scroll-mt-24">
          <Panel title="Team 16" description="Information Security & Cryptography (ISC) project.">
            <ul className="grid gap-3 sm:grid-cols-2">
              {TEAM.map(([n, r]) => (
                <li key={r} className="flex items-center justify-between rounded-lg border border-line px-4 py-3">
                  <span className="text-[14px] font-medium">{n}</span><span className="mono text-[12.5px] text-muted">{r}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </section>
      </div>
    </div>
  );
}
