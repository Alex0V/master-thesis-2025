package com.example.recipeapp.data.api

import com.example.recipeapp.data.manager.TokenManager
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

class RetrofitClient(private val tokenManager: TokenManager) {

    // 👇 Вставте сюди свій актуальний IP
    private val BASE_URL = "http://192.168.0.176:8000/api/v1/"

    // 1. Спеціальний API тільки для рефрешу (без Interceptor'ів, щоб не було вічного циклу)
    private val authApi: RecipeApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(RecipeApiService::class.java)
    }

    // 2. Основний API, яким ми користуємось
    val api: RecipeApiService by lazy {
        // Логування запитів (щоб бачити їх в Logcat)
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        // Створюємо нашого "рятувальника", передаючи йому чистий authApi
        val authenticator = TokenAuthenticator(tokenManager, authApi)

        // Налаштовуємо клієнт OkHttp
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(tokenManager)) // Додає токен
            .authenticator(authenticator)                  // Оновлює токен
            .addInterceptor(logging)                       // Пише логи
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        // Створюємо фінальний Retrofit
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(RecipeApiService::class.java)
    }
}