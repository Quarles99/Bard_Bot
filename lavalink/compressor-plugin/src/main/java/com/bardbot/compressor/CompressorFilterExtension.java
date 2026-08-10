package com.bardbot.compressor;

import com.sedmelluq.discord.lavaplayer.filter.FloatPcmAudioFilter;
import com.sedmelluq.discord.lavaplayer.format.AudioDataFormat;
import dev.arbjerg.lavalink.api.AudioFilterExtension;
import kotlinx.serialization.json.JsonElement;
import kotlinx.serialization.json.JsonObject;
import kotlinx.serialization.json.JsonPrimitive;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class CompressorFilterExtension implements AudioFilterExtension {
    private static final Logger LOG = LoggerFactory.getLogger(CompressorFilterExtension.class);

    public CompressorFilterExtension() {
        LOG.info("Loaded audio filter: compressor");
    }

    @NotNull
    @Override
    public String getName() {
        return "compressor";
    }

    @Nullable
    @Override
    public FloatPcmAudioFilter build(@NotNull JsonElement data, @Nullable AudioDataFormat format, @Nullable FloatPcmAudioFilter output) {
        if (format == null || output == null) {
            return null;
        }

        return new CompressorFilter(
                output,
                format.sampleRate,
                getFloat(data, "targetLevelDb", -16.0f),
                getFloat(data, "levelerAttackMs", 1000.0f),
                getFloat(data, "levelerReleaseMs", 4000.0f),
                getFloat(data, "levelerMaxBoostDb", 12.0f),
                getFloat(data, "levelerMaxCutDb", 24.0f),
                getFloat(data, "noiseGateDb", -50.0f),
                getFloat(data, "limiterThresholdDb", -1.0f),
                getFloat(data, "limiterAttackMs", 5.0f),
                getFloat(data, "limiterReleaseMs", 100.0f)
        );
    }

    @Override
    public boolean isEnabled(@NotNull JsonElement data) {
        return data instanceof JsonObject && !((JsonObject) data).isEmpty();
    }

    private static float getFloat(JsonElement data, String key, float defaultValue) {
        if (!(data instanceof JsonObject obj)) {
            return defaultValue;
        }

        JsonElement element = obj.get(key);

        if (!(element instanceof JsonPrimitive primitive)) {
            return defaultValue;
        }

        try {
            return Float.parseFloat(primitive.getContent());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
}
