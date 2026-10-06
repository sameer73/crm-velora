package com.shopcrm.app

import android.content.Context
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("shopcrm", Context.MODE_PRIVATE)

    var token: String?
        get() = prefs.getString("token", null)
        set(value) { prefs.edit().putString("token", value).apply() }

    var shopId: Long
        get() = prefs.getLong("shopId", 0L)
        set(value) { prefs.edit().putLong("shopId", value).apply() }

    var serverUrl: String
        get() = prefs.getString("server", "http://10.0.2.2:8000") ?: "http://10.0.2.2:8000"
        set(value) { prefs.edit().putString("server", value.trim().trimEnd('/')).apply() }
}

interface CrmApi {
    @GET("api/auth/status")
    suspend fun status(): StatusDto

    @POST("api/auth/setup")
    suspend fun setup(@Body body: SetupRequest): AuthDto

    @POST("api/auth/login")
    suspend fun login(@Body body: LoginRequest): AuthDto

    @GET("api/auth/me")
    suspend fun me(): UserDto

    @GET("api/shops")
    suspend fun shops(): List<ShopDto>

    @POST("api/shops")
    suspend fun createShop(@Body body: ShopRequest): ShopDto

    @POST("api/users")
    suspend fun createStaff(@Body body: StaffRequest): UserDto

    @POST("api/items")
    suspend fun createItem(@Body body: ItemRequest): Map<String, Any>

    @GET("api/shops/{shopId}/stock")
    suspend fun stock(@Path("shopId") shopId: Long): List<StockRowDto>

    @POST("api/shops/{shopId}/stock/adjust")
    suspend fun adjust(@Path("shopId") shopId: Long, @Body body: AdjustRequest): StockRowDto

    @GET("api/vendors")
    suspend fun vendors(): List<VendorDto>

    @POST("api/vendors")
    suspend fun createVendor(@Body body: VendorRequest): VendorDto

    @GET("api/shops/{shopId}/customers")
    suspend fun customers(@Path("shopId") shopId: Long): List<CustomerDto>

    @POST("api/shops/{shopId}/customers")
    suspend fun createCustomer(@Path("shopId") shopId: Long, @Body body: CustomerRequest): CustomerDto

    @GET("api/shops/{shopId}/purchases")
    suspend fun purchases(@Path("shopId") shopId: Long): List<PurchaseDto>

    @POST("api/shops/{shopId}/purchases")
    suspend fun createPurchase(@Path("shopId") shopId: Long, @Body body: PurchaseRequest): PurchaseDto

    @GET("api/shops/{shopId}/bills")
    suspend fun bills(@Path("shopId") shopId: Long): List<BillDto>

    @POST("api/shops/{shopId}/bills")
    suspend fun createBill(@Path("shopId") shopId: Long, @Body body: BillRequest): BillDto

    @GET("api/shops/{shopId}/bills/{id}")
    suspend fun bill(@Path("shopId") shopId: Long, @Path("id") id: Long): BillDto

    @GET("api/shops/{shopId}/today")
    suspend fun today(@Path("shopId") shopId: Long): TodayDto

    @GET("api/shops/{shopId}/wallet")
    suspend fun wallet(@Path("shopId") shopId: Long, @Query("date") date: String): WalletDto

    @POST("api/shops/{shopId}/wallet")
    suspend fun addLedger(@Path("shopId") shopId: Long, @Body body: LedgerRequest): LedgerDto
}

fun buildApi(store: SessionStore): CrmApi {
    val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val token = store.token
            val request = if (token.isNullOrBlank()) {
                chain.request()
            } else {
                chain.request().newBuilder().header("Authorization", "Bearer $token").build()
            }
            chain.proceed(request)
        }
        .build()
    val gson: Gson = GsonBuilder().create()
    return Retrofit.Builder()
        .baseUrl(store.serverUrl.trimEnd('/') + "/")
        .client(client)
        .addConverterFactory(GsonConverterFactory.create(gson))
        .build()
        .create(CrmApi::class.java)
}

fun httpMessage(error: Throwable): String {
    if (error is HttpException) {
        val raw = error.response()?.errorBody()?.string().orEmpty()
        val detail = runCatching {
            Gson().fromJson(raw, Map::class.java)?.get("detail")?.toString()
        }.getOrNull()
        if (!detail.isNullOrBlank() && detail != "null") return detail
        return "Request failed (${error.code()})"
    }
    return error.message ?: "Cannot reach the server. Check the address in More."
}
