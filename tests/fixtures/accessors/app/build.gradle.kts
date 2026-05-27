plugins {
    id("com.android.application")
}

dependencies {
    // Type-safe project accessors (Gradle 7+)
    implementation(projects.feature.paymentsCommon)
    api(projects.core.networkApi)

    // Mezcla: el formato clásico tambien debe seguir funcionando en el mismo archivo
    implementation(project(":legacy:plain-lib"))
}
