plugins {
    id("com.android.application")
}

dependencies {
    implementation(
        project(":core")
    )
    api(
        project(
            ":shared"
        )
    )
    testImplementation(project(":core"))
}
