package com.shopcrm.app

import java.util.ArrayDeque

fun formatInr(paise: Long): String {
    val sign = if (paise < 0) "-" else ""
    val abs = kotlin.math.abs(paise)
    val rupees = abs / 100
    val frac = abs % 100
    val digits = rupees.toString()
    val grouped = if (digits.length <= 3) {
        digits
    } else {
        val tail = digits.takeLast(3)
        var head = digits.dropLast(3)
        val parts = ArrayDeque<String>()
        while (head.isNotEmpty()) {
            parts.addFirst(head.takeLast(2))
            head = head.dropLast(2)
        }
        parts.joinToString(",") + "," + tail
    }
    return "$sign₹$grouped.${frac.toString().padStart(2, '0')}"
}

fun rupeesToPaise(text: String): Long? {
    val cleaned = text.trim().replace(",", "").replace("₹", "")
    if (!Regex("""\d+(\.\d{1,2})?""").matches(cleaned)) return null
    val parts = cleaned.split(".")
    val frac = if (parts.size == 2) parts[1].padEnd(2, '0') else "00"
    return parts[0].toLong() * 100 + frac.take(2).toLong()
}

fun paiseInput(paise: Long): String {
    val rupees = kotlin.math.abs(paise) / 100
    val frac = kotlin.math.abs(paise) % 100
    return "$rupees.${frac.toString().padStart(2, '0')}"
}
