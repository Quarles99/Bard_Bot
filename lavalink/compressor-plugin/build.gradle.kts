plugins {
    java
    id("dev.arbjerg.lavalink.gradle-plugin") version "1.1.2"
}

group = "com.bardbot.compressor"
version = "0.1.0"

lavalinkPlugin {
    name = "compressor-plugin"
    apiVersion = "4.2.2"
    serverVersion = "4.2.2"
    configurePublishing = false
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(17)
    }
}

repositories {
    mavenCentral()
}

tasks {
    compileJava {
        options.encoding = "UTF-8"
    }
}
