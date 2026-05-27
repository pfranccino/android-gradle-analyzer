plugins { id("com.android.library") }

dependencies {
    // Refiere al :common RAÍZ — NO debe contarse como caller de target:common.
    // Antes del fix, el matcher con endswith reportaba un falso positivo.
    implementation(project(":common"))

    // Llamada real a un submódulo de target → debe aparecer en external_callers.
    implementation(project(":target:common"))
}
