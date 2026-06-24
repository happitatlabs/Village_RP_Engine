import org.gradle.api.tasks.Sync

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

val repoRoot = layout.projectDirectory.dir("../..")
val generatedPythonDir = layout.buildDirectory.dir("generated/python")

val syncPythonSources by tasks.registering(Sync::class) {
    from(repoRoot.file("web_ui.py"))
    from(repoRoot.dir("village_rp_engine")) {
        into("village_rp_engine")
        exclude("tests/**")
        exclude("**/__pycache__/**")
        exclude("**/*.pyc")
    }
    into(generatedPythonDir)
}

android {
    namespace = "com.villagerpengine.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.villagerpengine.mobile"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

chaquopy {
    defaultConfig {
        version = "3.10"
        buildPython("C:/Users/Hyein/AppData/Local/Programs/Python/Python310/python.exe")
    }
    sourceSets {
        getByName("main") {
            srcDir(generatedPythonDir)
        }
    }
}

tasks.named("preBuild").configure {
    dependsOn(syncPythonSources)
}

tasks.matching { it.name != "syncPythonSources" && it.name.endsWith("PythonSources") }.configureEach {
    dependsOn(syncPythonSources)
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.11.0")
    implementation("com.google.android.material:material:1.12.0")
}
