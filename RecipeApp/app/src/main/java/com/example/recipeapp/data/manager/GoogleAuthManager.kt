package com.example.recipeapp.data.manager

import android.content.Context
import android.util.Log
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialException
import com.example.recipeapp.R
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential

class GoogleAuthManager(private val context: Context) {
    private val credentialManager = CredentialManager.Companion.create(context)

    suspend fun signIn(): String? {
        // 1. Отримуємо ваш Client ID з ресурсів
        val webClientId = context.getString(R.string.google_web_client_id)

        // 2. Налаштовуємо запит до Google
        val googleIdOption = GetGoogleIdOption.Builder()
            .setFilterByAuthorizedAccounts(false) // Показувати всі акаунти, а не тільки ті, що вже входили
            .setServerClientId(webClientId)
            .setAutoSelectEnabled(false) // Не входити автоматично, дати користувачу вибрати
            .build()

        val request = GetCredentialRequest.Builder()
            .addCredentialOption(googleIdOption)
            .build()

        return try {
            // 3. Показуємо вікно вибору акаунту
            val result = credentialManager.getCredential(
                request = request,
                context = context
            )

            // 4. Розбираємо результат
            val credential = result.credential
            if (credential is CustomCredential && credential.type == GoogleIdTokenCredential.Companion.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
                val googleIdTokenCredential = GoogleIdTokenCredential.Companion.createFrom(credential.data)
                // 5. Повертаємо ID Token (це саме те, що треба нашому серверу)
                googleIdTokenCredential.idToken
            } else {
                Log.e("GoogleAuth", "Unexpected credential type")
                null
            }
        } catch (e: GetCredentialException) {
            Log.e("GoogleAuth", "Error: ${e.message}")
            null // Користувач скасував вхід або сталася помилка
        } catch (e: Exception) {
            Log.e("GoogleAuth", "Unknown Error: ${e.message}")
            null
        }
    }
}