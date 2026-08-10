package com.bardbot.compressor;

import com.sedmelluq.discord.lavaplayer.filter.FloatPcmAudioFilter;

/**
 * Two-stage loudness compressor: a slow "leveler" (AGC) that tracks each
 * track's running loudness across all channels together and drives it
 * toward {@code targetLevelDb}, so a quietly-mastered track and a loud one
 * end up sounding similarly loud; and a fast limiter on top of that as a
 * safety net so the leveler's makeup gain never clips a sudden loud
 * passage.
 *
 * <p>The leveler's envelope is asymmetric: it rises quickly when the signal
 * gets louder (so the makeup gain backs off before a loud section clips)
 * and falls slowly when the signal gets quieter (so a brief pause doesn't
 * make the leveler rush to boost it). A noise gate additionally freezes the
 * envelope during near-silence (intros, dead air, fades) so those sections
 * don't wind the gain up toward {@code levelerMaxBoostDb}.
 *
 * <p>All math in the per-sample hot path is linear-domain (no {@code log10}/
 * {@code pow}/{@code sqrt} per sample); dB parameters are converted to
 * linear gain/level once, in the constructor.
 */
public class CompressorFilter implements FloatPcmAudioFilter {
    private static final float EPS = 1e-9f;

    private final FloatPcmAudioFilter downstream;

    private final float targetLinear;
    private final float maxGainLinear;
    private final float minGainLinear;
    private final float noiseGateLinear;
    private final float limiterThresholdLinear;

    private final float levelerAttackCoeff;
    private final float levelerReleaseCoeff;
    private final float limiterAttackCoeff;
    private final float limiterReleaseCoeff;

    private float levelerEnvelope;
    private float limiterEnvelope;

    public CompressorFilter(
            FloatPcmAudioFilter downstream,
            int sampleRate,
            float targetLevelDb,
            float levelerAttackMs,
            float levelerReleaseMs,
            float levelerMaxBoostDb,
            float levelerMaxCutDb,
            float noiseGateDb,
            float limiterThresholdDb,
            float limiterAttackMs,
            float limiterReleaseMs
    ) {
        this.downstream = downstream;

        this.targetLinear = dbToLinear(targetLevelDb);
        this.maxGainLinear = dbToLinear(levelerMaxBoostDb);
        this.minGainLinear = dbToLinear(-levelerMaxCutDb);
        this.noiseGateLinear = dbToLinear(noiseGateDb);
        this.limiterThresholdLinear = dbToLinear(limiterThresholdDb);

        this.levelerAttackCoeff = onePoleCoeff(levelerAttackMs, sampleRate);
        this.levelerReleaseCoeff = onePoleCoeff(levelerReleaseMs, sampleRate);
        this.limiterAttackCoeff = onePoleCoeff(limiterAttackMs, sampleRate);
        this.limiterReleaseCoeff = onePoleCoeff(limiterReleaseMs, sampleRate);

        this.levelerEnvelope = targetLinear;
        this.limiterEnvelope = 0.0f;
    }

    private static float onePoleCoeff(float timeConstantMs, int sampleRate) {
        return (float) Math.exp(-1000.0 / (Math.max(timeConstantMs, 1.0f) * sampleRate));
    }

    private static float dbToLinear(float db) {
        return (float) Math.pow(10.0, db / 20.0);
    }

    private static float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }

    @Override
    public void process(float[][] input, int offset, int length) throws InterruptedException {
        int channels = input.length;

        for (int i = offset; i < offset + length; i++) {
            // Leveler: track long-term loudness across all channels together
            // (not per-channel, so stereo balance isn't disturbed), and drive
            // it toward targetLinear. Asymmetric + gated, see class doc.
            float frameAbs = 0.0f;
            for (int c = 0; c < channels; c++) {
                frameAbs += Math.abs(input[c][i]);
            }
            frameAbs /= channels;

            if (frameAbs >= noiseGateLinear) {
                float coeff = frameAbs > levelerEnvelope ? levelerAttackCoeff : levelerReleaseCoeff;
                levelerEnvelope = coeff * levelerEnvelope + (1 - coeff) * frameAbs;
            }

            float levelerGain = clamp(targetLinear / Math.max(levelerEnvelope, EPS), minGainLinear, maxGainLinear);

            // Limiter: fast safety net on the post-leveler peak, so the
            // leveler's makeup gain never causes a sudden loud passage to clip.
            float peak = 0.0f;
            for (int c = 0; c < channels; c++) {
                peak = Math.max(peak, Math.abs(input[c][i] * levelerGain));
            }
            if (peak > limiterEnvelope) {
                limiterEnvelope = limiterAttackCoeff * limiterEnvelope + (1 - limiterAttackCoeff) * peak;
            } else {
                limiterEnvelope = limiterReleaseCoeff * limiterEnvelope + (1 - limiterReleaseCoeff) * peak;
            }
            float limiterGain = Math.min(1.0f, limiterThresholdLinear / Math.max(limiterEnvelope, EPS));

            float totalGain = levelerGain * limiterGain;
            for (int c = 0; c < channels; c++) {
                input[c][i] = clamp(input[c][i] * totalGain, -1.0f, 1.0f);
            }
        }

        downstream.process(input, offset, length);
    }

    @Override
    public void seekPerformed(long requestedTime, long providedTime) {
        levelerEnvelope = targetLinear;
        limiterEnvelope = 0.0f;
    }

    @Override
    public void flush() {
        levelerEnvelope = targetLinear;
        limiterEnvelope = 0.0f;
    }

    @Override
    public void close() {
    }
}
