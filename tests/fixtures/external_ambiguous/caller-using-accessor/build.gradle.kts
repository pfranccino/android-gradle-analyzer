plugins { id("com.android.library") }

dependencies {
    // Caller externo que usa type-safe accessor para llamar a target:common.
    // Debe detectarse igual que la sintaxis clásica.
    implementation(projects.target.common)
}
