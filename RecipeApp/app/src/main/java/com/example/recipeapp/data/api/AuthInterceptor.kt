package com.example.recipeapp.data.api

import com.example.recipeapp.data.manager.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        // runBlocking дозволяє отримати дані з DataStore синхронно (це безпечно тут, бо Retrofit вже у фоні)
        val token = runBlocking {
            tokenManager.accessToken.first()
        }

        val requestBuilder = chain.request().newBuilder()

        // Якщо токен є — додаємо заголовок Authorization
        if (!token.isNullOrBlank()) {
            requestBuilder.addHeader("Authorization", "Bearer $token")
        }

        return chain.proceed(requestBuilder.build())
    }
}