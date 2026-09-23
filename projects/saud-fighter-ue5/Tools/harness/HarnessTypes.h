#pragma once
/**
 * Just enough of Unreal to execute the pure geometry outside it.
 *
 * The same idea as the Unity port's `Tools/harness/UnityEngine.cs`: this
 * build has never been compiled by an engine and there is no way to get one
 * here, so everything that can be separated from the engine is, and this is
 * what it is compiled against. It is deliberately small — if a test needs a
 * component, an actor or a world, the thing under test is in the wrong file.
 */
#include <cmath>
#include <cstdio>

struct FVector
{
    float X = 0.f, Y = 0.f, Z = 0.f;
    FVector() {}
    FVector(float InX, float InY, float InZ) : X(InX), Y(InY), Z(InZ) {}
    FVector operator+(const FVector& O) const { return FVector(X + O.X, Y + O.Y, Z + O.Z); }
    FVector operator-(const FVector& O) const { return FVector(X - O.X, Y - O.Y, Z - O.Z); }
    FVector operator*(float S) const { return FVector(X * S, Y * S, Z * S); }
    FVector operator/(float S) const { return FVector(X / S, Y / S, Z / S); }
    FVector operator-() const { return FVector(-X, -Y, -Z); }
    FVector& operator+=(const FVector& O) { X += O.X; Y += O.Y; Z += O.Z; return *this; }
    float Size2D() const { return std::sqrt(X * X + Y * Y); }
    float Size() const { return std::sqrt(X * X + Y * Y + Z * Z); }
    float SizeSquared() const { return X * X + Y * Y + Z * Z; }
    bool IsNearlyZero(float Tol = 1e-4f) const { return std::fabs(X) <= Tol && std::fabs(Y) <= Tol && std::fabs(Z) <= Tol; }
    FVector GetSafeNormal(float Tol = 1e-8f) const
    {
        const float S = SizeSquared();
        return S <= Tol ? FVector(0.f, 0.f, 0.f) : *this / std::sqrt(S);
    }
    static float DotProduct(const FVector& A, const FVector& B) { return A.X * B.X + A.Y * B.Y + A.Z * B.Z; }
    static FVector CrossProduct(const FVector& A, const FVector& B)
    {
        return FVector(A.Y * B.Z - A.Z * B.Y, A.Z * B.X - A.X * B.Z, A.X * B.Y - A.Y * B.X);
    }
    static float Dist(const FVector& A, const FVector& B) { return (A - B).Size(); }
    static FVector ZeroVector;
    static FVector UpVector;
};
inline FVector FVector::ZeroVector = FVector(0.f, 0.f, 0.f);
inline FVector FVector::UpVector = FVector(0.f, 0.f, 1.f);

namespace FMath
{
    inline float Sqrt(float V) { return std::sqrt(V); }
    inline float Abs(float V) { return V < 0.f ? -V : V; }
    inline float Cos(float V) { return std::cos(V); }
    inline float Sin(float V) { return std::sin(V); }
    inline float Atan2(float A, float B) { return std::atan2(A, B); }
    inline float DegreesToRadians(float D) { return D * 3.14159265358979f / 180.f; }
    inline float RadiansToDegrees(float R) { return R * 180.f / 3.14159265358979f; }
    inline float Min(float A, float B) { return A < B ? A : B; }
    inline float Max(float A, float B) { return A > B ? A : B; }
    inline float Clamp(float V, float A, float B) { return V < A ? A : (V > B ? B : V); }
    inline float Square(float V) { return V * V; }
    inline float Exp(float V) { return std::exp(V); }
    inline float Acos(float V) { return std::acos(V < -1.f ? -1.f : (V > 1.f ? 1.f : V)); }
    inline float Lerp(float A, float B, float T) { return A + (B - A) * T; }
    inline bool IsNearlyEqual(float A, float B, float Tol = 1e-4f) { return std::fabs(A - B) <= Tol; }
}
